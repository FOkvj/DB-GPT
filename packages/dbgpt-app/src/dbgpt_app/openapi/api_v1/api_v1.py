import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from concurrent.futures import Executor

from typing import List, Optional, cast

import pandas as pd
from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt.component import ComponentType
from dbgpt.configs import TAG_KEY_KNOWLEDGE_CHAT_DOMAIN_TYPE
from dbgpt.core import ModelOutput
from dbgpt.core.awel import BaseOperator, CommonLLMHttpRequestBody
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.core.awel.util.chat_util import safe_chat_stream_with_dag_task
from dbgpt.core.interface.file import FileStorageClient
from dbgpt.core.schema.api import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    DeltaMessage,
    UsageInfo,
)
from dbgpt._private.pydantic import BaseModel
from dbgpt.model.base import FlatSupportedModel
from dbgpt.model.cluster import BaseModelController, WorkerManager, WorkerManagerFactory
from dbgpt.util.executor_utils import (
    DefaultExecutorFactory,
    ExecutorFactory,
)
from dbgpt.util.file_client import FileClient
from dbgpt.util.tracer import SpanType, root_tracer
from dbgpt_app.expend.excel2db import ExtendedMySQLConnector, ExcelToMysql
from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest
from dbgpt_app.knowledge.service import KnowledgeService
from dbgpt_app.openapi.api_view_model import (
    ChatSceneVo,
    ConversationVo,
    MessageVo,
    Result,
)
from dbgpt_app.scene import BaseChat, ChatFactory, ChatParam, ChatScene
from dbgpt_serve.agent.db.gpts_app import UserRecentAppsDao, adapt_native_app_model
from dbgpt_serve.core import blocking_func_to_async
from dbgpt_serve.datasource.manages.db_conn_info import DBConfig, DbTypeInfo
from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient
from dbgpt_serve.flow.service.service import Service as FlowService
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers
from fastapi import Form
from sqlalchemy import create_engine, inspect, text


router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = logging.getLogger(__name__)
knowledge_service = KnowledgeService()

model_semaphore = None
global_counter = 0


user_recent_app_dao = UserRecentAppsDao()


def __get_conv_user_message(conversations: dict):
    messages = conversations["messages"]
    for item in messages:
        if item["type"] == "human":
            return item["data"]["content"]
    return ""


def __new_conversation(chat_mode, user_name: str, sys_code: str) -> ConversationVo:
    unique_id = uuid.uuid1()
    return ConversationVo(
        conv_uid=str(unique_id),
        chat_mode=chat_mode,
        user_name=user_name,
        sys_code=sys_code,
    )


def get_db_list(user_id: str = None):
    dbs = CFG.local_db_manager.get_db_list(user_id=user_id)
    db_params = []
    for item in dbs:
        params: dict = {}
        params.update({"param": item["db_name"]})
        params.update({"type": item["db_type"]})
        db_params.append(params)
    return db_params


def plugins_select_info():
    plugins_infos: dict = {}
    for plugin in CFG.plugins:
        plugins_infos.update(
            {f"【{plugin._name}】=>{plugin._description}": plugin._name}
        )
    return plugins_infos


def get_db_list_info(user_id: str = None):
    dbs = CFG.local_db_manager.get_db_list(user_id=user_id)
    params: dict = {}
    for item in dbs:
        comment = item["comment"]
        if comment is not None and len(comment) > 0:
            params.update({item["db_name"]: comment})
    return params


def knowledge_list_info():
    """return knowledge space list"""
    params: dict = {}
    request = KnowledgeSpaceRequest()
    spaces = knowledge_service.get_knowledge_space(request)
    for space in spaces:
        params.update({space.name: space.desc})
    return params


def knowledge_list(user_id: str = None):
    """return knowledge space list"""
    request = KnowledgeSpaceRequest(user_id=user_id)
    spaces = knowledge_service.get_knowledge_space(request)
    space_list = []
    for space in spaces:
        params: dict = {}
        params.update({"param": space.name})
        params.update({"type": "space"})
        params.update({"space_id": space.id})
        space_list.append(params)
    return space_list


def get_model_controller() -> BaseModelController:
    controller = CFG.SYSTEM_APP.get_component(
        ComponentType.MODEL_CONTROLLER, BaseModelController
    )
    return controller


def get_worker_manager() -> WorkerManager:
    worker_manager = CFG.SYSTEM_APP.get_component(
        ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
    ).create()
    return worker_manager


def get_fs() -> FileStorageClient:
    return FileStorageClient.get_instance(CFG.SYSTEM_APP)


def get_dag_manager() -> DAGManager:
    """Get the global default DAGManager"""
    return DAGManager.get_instance(CFG.SYSTEM_APP)


def get_chat_flow() -> FlowService:
    """Get Chat Flow Service."""
    return FlowService.get_instance(CFG.SYSTEM_APP)


def get_executor() -> Executor:
    """Get the global default executor"""
    return CFG.SYSTEM_APP.get_component(
        ComponentType.EXECUTOR_DEFAULT,
        ExecutorFactory,
        or_register_component=DefaultExecutorFactory,
    ).create()


@router.get("/v1/chat/db/list", response_model=Result)
async def db_connect_list(
    db_name: Optional[str] = Query(default=None, description="database name"),
    user_info: UserRequest = Depends(get_user_from_headers),
):
    results = CFG.local_db_manager.get_db_list(
        db_name=db_name, user_id=user_info.user_id
    )
    # 排除部分数据库不允许用户访问
    if results and len(results):
        results = [
            d
            for d in results
            if d.get("db_name") not in ["auth", "dbgpt", "test", "public"]
        ]
    return Result.succ(results)


@router.post("/v1/chat/db/add", response_model=Result)
async def db_connect_add(
    db_config: DBConfig = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    return Result.succ(CFG.local_db_manager.add_db(db_config, user_token.user_id))


@router.get("/v1/permission/db/list", response_model=Result[List])
async def permission_db_list(
    db_name: str = None,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    return Result.succ()


@router.post("/v1/chat/db/edit", response_model=Result)
async def db_connect_edit(
    db_config: DBConfig = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    return Result.succ(CFG.local_db_manager.edit_db(db_config))


@router.post("/v1/chat/db/delete", response_model=Result[bool])
async def db_connect_delete(db_name: str = None):
    CFG.local_db_manager.db_summary_client.delete_db_profile(db_name)
    return Result.succ(CFG.local_db_manager.delete_db(db_name))


@router.post("/v1/chat/db/refresh", response_model=Result[bool])
async def db_connect_refresh(db_config: DBConfig = Body()):
    CFG.local_db_manager.db_summary_client.delete_db_profile(db_config.db_name)
    success = await CFG.local_db_manager.async_db_summary_embedding(
        db_config.db_name, db_config.db_type
    )
    return Result.succ(success)


async def async_db_summary_embedding(db_name, db_type):
    db_summary_client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
    db_summary_client.db_summary_embedding(db_name, db_type)


@router.post("/v1/chat/db/test/connect", response_model=Result[bool])
async def test_connect(
    db_config: DBConfig = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    try:
        # TODO Change the synchronous call to the asynchronous call
        CFG.local_db_manager.test_connect(db_config)
        return Result.succ(True)
    except Exception as e:
        return Result.failed(code="E1001", msg=str(e))


@router.post("/v1/chat/db/summary", response_model=Result[bool])
async def db_summary(db_name: str, db_type: str):
    # TODO Change the synchronous call to the asynchronous call
    async_db_summary_embedding(db_name, db_type)
    return Result.succ(True)


@router.get("/v1/chat/db/support/type", response_model=Result[List[DbTypeInfo]])
async def db_support_types():
    support_types = CFG.local_db_manager.get_all_completed_types()
    db_type_infos = []
    for type in support_types:
        db_type_infos.append(
            DbTypeInfo(db_type=type.value(), is_file_db=type.is_file_db())
        )
    return Result[DbTypeInfo].succ(db_type_infos)


@router.post("/v1/chat/dialogue/scenes", response_model=Result[List[ChatSceneVo]])
async def dialogue_scenes(user_info: UserRequest = Depends(get_user_from_headers)):
    scene_vos: List[ChatSceneVo] = []
    new_modes: List[ChatScene] = [
        ChatScene.ChatWithDbExecute,
        ChatScene.ChatWithDbQA,
        ChatScene.ChatExcel,
        ChatScene.ChatKnowledge,
        ChatScene.ChatDashboard,
        ChatScene.ChatAgent,
    ]
    for scene in new_modes:
        scene_vo = ChatSceneVo(
            chat_scene=scene.value(),
            scene_name=scene.scene_name(),
            scene_describe=scene.describe(),
            param_title=",".join(scene.param_types()),
            show_disable=scene.show_disable(),
        )
        scene_vos.append(scene_vo)
    return Result.succ(scene_vos)


@router.post("/v1/resource/params/list", response_model=Result[List[dict]])
async def resource_params_list(
    resource_type: str,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    if resource_type == "database":
        result = get_db_list()
    elif resource_type == "knowledge":
        result = knowledge_list()
    elif resource_type == "tool":
        result = plugins_select_info()
    else:
        return Result.succ()
    return Result.succ(result)


@router.post("/v1/chat/mode/params/list", response_model=Result[List[dict]])
async def params_list(
    chat_mode: str = ChatScene.ChatNormal.value(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    if ChatScene.ChatWithDbQA.value() == chat_mode:
        result = get_db_list()
    elif ChatScene.ChatWithDbExecute.value() == chat_mode:
        result = get_db_list()
    elif ChatScene.ChatDashboard.value() == chat_mode:
        result = get_db_list()
    elif ChatScene.ChatExecution.value() == chat_mode:
        result = plugins_select_info()
    elif ChatScene.ChatKnowledge.value() == chat_mode:
        result = knowledge_list()
    elif ChatScene.ChatKnowledge.ExtractRefineSummary.value() == chat_mode:
        result = knowledge_list()
    else:
        return Result.succ()
    return Result.succ(result)


@router.post("/v1/resource/oss_file/delete")
async def oss_file_delete(
    uri: str,
    fs: FileStorageClient = Depends(get_fs),
):
    status = fs.delete_file(uri)
    if status:
        return Result.succ(status)
    return Result.failed(msg=f"{uri} 指定资源不存在！")

@router.post("/v1/resource/file/upload")
async def file_upload(
    chat_mode: str,
    conv_uid: str,
    temperature: Optional[float] = None,
    max_new_tokens: Optional[int] = None,
    sys_code: Optional[str] = None,
    model_name: Optional[str] = None,
    doc_files: List[UploadFile] = File(...),
    user_token: UserRequest = Depends(get_user_from_headers),
    fs: FileStorageClient = Depends(get_fs),
):
    logger.info(
        f"file_upload:{conv_uid}, files:{[file.filename for file in doc_files]}"
    )

    bucket = "dbgpt_app_file"
    file_params = []

    for doc_file in doc_files:
        file_name = doc_file.filename
        custom_metadata = {
            "user_name": user_token.user_id,
            "sys_code": sys_code,
            "conv_uid": conv_uid,
        }

        file_uri = await blocking_func_to_async(
            CFG.SYSTEM_APP,
            fs.save_file,
            bucket,
            file_name,
            doc_file.file,
            custom_metadata=custom_metadata,
        )

        _, file_extension = os.path.splitext(file_name)
        file_param = {
            "is_oss": True,
            "file_path": file_uri,
            "file_name": file_name,
            "file_learning": False,
            "bucket": bucket,
        }
        file_params.append(file_param)
    if chat_mode == ChatScene.ChatExcel.value():
        if len(file_params) != 1:
            return Result.failed(msg="Only one file is supported for Excel chat.")
        file_param = file_params[0]
        _, file_extension = os.path.splitext(file_param["file_name"])
        if file_extension.lower() in [".xls", ".xlsx", ".csv", ".json", ".parquet"]:
            # Prepare the chat
            file_param["file_learning"] = True
            dialogue = ConversationVo(
                user_input="Learn from the file",
                conv_uid=conv_uid,
                chat_mode=chat_mode,
                select_param=file_param,
                model_name=model_name,
                user_name=user_token.user_id,
                sys_code=sys_code,
            )

            if temperature is not None:
                dialogue.temperature = temperature
            if max_new_tokens is not None:
                dialogue.max_new_tokens = max_new_tokens

            chat: BaseChat = await get_chat_instance(dialogue)
            await chat.prepare()
            # Refresh messages

    # If only one file was uploaded, return the single file_param directly
    # Otherwise return the array of file_params
    result = file_params[0] if len(file_params) == 1 else file_params
    return Result.succ(result)


@router.post("/v1/resource/file/delete")
async def file_delete(
    conv_uid: str,
    file_key: str,
    user_name: Optional[str] = None,
    sys_code: Optional[str] = None,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(f"file_delete:{conv_uid},{file_key}")
    oss_file_client = FileClient()

    return Result.succ(
        await oss_file_client.delete_file(conv_uid=conv_uid, file_key=file_key)
    )


# @router.post("/v1/expand/dataprocess/excel2db")
# async def excel2db(
#         # 通过Query从URL中获取的参数
#         dbType: str = Query(..., description="数据库类型"),
#         dbHost: str = Query(..., description="数据库主机"),
#         dbPort: int = Query(3306, description="数据库端口"),
#         dbName: str = Query(..., description="数据库名称"),
#         dbUser: str = Query(..., description="数据库用户名"),
#         autoCreate: str = Query(..., description="是否自动创建库或表"),
#         chunkSize: str = Query(..., description="数据块大小"),
#         ifExists: str = Query(..., description="如果已存在的处理方式"),
#
#         # 可选的Query参数
#         sheetNames: Optional[str] = Query(None, description="工作表名称，多个用逗号分隔"),
#         tablePrefix: Optional[str] = Query(None, description="表前缀"),
#         tableMapping: Optional[str] = Query(None, description="表映射关系"),
#         columnMapping: Optional[str] = Query(None, description="列映射关系"),
#
#         # 通过Form从请求体中获取的敏感参数
#         dbPassword: str = Form(..., description="数据库密码"),
#
#         # 文件上传
#         files: List[UploadFile] = File(..., description="Excel文件")
# ):
#     """
#     处理Excel文件并导入到数据库
#
#     - 从URL查询参数中获取大部分配置信息
#     - 从表单数据中获取敏感信息（如密码）
#     - 处理上传的Excel文件并将其导入到MySQL数据库
#     """
#     logger.info(f"处理Excel到数据库导入：{dbType}, {dbHost}:{dbPort}, {dbName}")
#
#     # 转换字符串参数为相应的类型
#     chunk_size = int(chunkSize)
#     auto_create = autoCreate.lower() in ('是', 'yes', 'true', '1')
#
#     # 解析可选参数
#     sheet_names_list = None
#     if sheetNames:
#         sheet_names_list = [s.strip() for s in sheetNames.split(',')]
#
#     table_mapping_dict = None
#     if tableMapping:
#         try:
#             table_mapping_dict = json.loads(tableMapping)
#         except json.JSONDecodeError:
#             return {
#                 "success": False,
#                 "err_code": "E0002",
#                 "err_msg": "表映射JSON格式错误",
#                 "data": None
#             }
#
#     column_mapping_dict = None
#     if columnMapping:
#         try:
#             column_mapping_dict = json.loads(columnMapping)
#         except json.JSONDecodeError:
#             return Result.failed(code="E0003", msg="列映射JSON格式错误")
#
#     # 验证其他参数
#     if ifExists not in ['fail', 'replace', 'append']:
#         return Result.failed(code="E0005", msg="ifExists必须是'fail'、'replace'或'append'之一")
#
#     # 创建一个临时目录来存储上传的文件
#     temp_dir = tempfile.mkdtemp()
#     try:
#         # 处理上传的所有文件
#         all_results = {
#             "files": [],
#             "success": True,
#             "fileCount": len(files),
#             "totalRows": 0,
#             "processedRows": 0,
#             "failedRows": 0,
#             "dbInfo": {
#                 "dbName": dbName,
#                 "tables": []  # 用于存储表名和结构信息
#             }
#         }
#
#         # # 用于临时存储表字段映射信息
#         # table_data = []
#
#         # 创建MySQL连接器
#         try:
#             connector = ExtendedMySQLConnector.from_uri_db(
#                 host=dbHost,
#                 port=dbPort,
#                 user=dbUser,
#                 pwd=dbPassword,
#                 db_name=dbName,
#                 auto_create=auto_create
#             )
#         except Exception as e:
#             logger.error(f"数据库连接错误: {str(e)}")
#             return Result.failed(code="E0005", msg=f"数据库连接错误: {str(e)}")
#
#         # 用于存储所有处理过的表信息
#         processed_tables = set()
#
#         for file in files:
#             # 将上传的文件保存到临时目录
#             file_path = os.path.join(temp_dir, file.filename)
#             with open(file_path, "wb") as buffer:
#                 shutil.copyfileobj(file.file, buffer)
#
#             # 创建Excel导入器并处理文件
#             try:
#                 importer = ExcelToMysql.from_connector(
#                     connector=connector,
#                     excel_path_buffer=file_path,
#                     auto_create=auto_create,
#                     sheet_names=sheet_names_list,
#                     table_prefix=tablePrefix or "",
#                     table_mapping=table_mapping_dict,
#                     chunk_size=chunk_size,
#                     if_exists=ifExists,
#                     column_mapping=column_mapping_dict
#                 )
#
#                 # 导入Excel文件
#                 file_result = importer.import_excel()
#
#                 # 收集处理过的表信息
#                 for sheet_name, sheet_result in file_result["sheets"].items():
#                     if sheet_result["success"]:
#                         table_name = importer._get_table_name(sheet_name)
#                         processed_tables.add(table_name)
#
#                 # # 提取表结构信息用于前端展示（只提取第一个表的信息作为table_data）
#                 # if table_data == [] and file_result["success"]:
#                 #     # 获取第一个工作表的名称
#                 #     first_sheet_name = next(iter(file_result["sheets"]))
#                 #     sheet_result = file_result["sheets"][first_sheet_name]
#                 #
#                 #     # 如果成功，则获取表结构
#                 #     if sheet_result["success"]:
#                 #         table_name = importer._get_table_name(first_sheet_name)
#                 #         inspector = inspect(connector._engine)
#                 #         columns = inspector.get_columns(table_name)
#                 #
#                 #         # 格式化列信息以供前端显示（用于旧的tableData结构）
#                 #         for i, col in enumerate(columns):
#                 #             table_data.append({
#                 #                 "key": str(i + 1),
#                 #                 "column": col["name"],
#                 #                 "type": str(col["type"]),
#                 #                 "mapped": col.get("mapped", col["name"])
#                 #             })
#
#                 # 计算总计数据
#                 processed_rows = sum(sheet["rows_processed"] for sheet in file_result["sheets"].values())
#                 imported_rows = sum(sheet["rows_imported"] for sheet in file_result["sheets"].values())
#                 failed_rows = processed_rows - imported_rows
#
#                 # 添加到结果集
#                 file_info = {
#                     "fileName": file.filename,
#                     "bucket": "local",
#                     "totalRows": processed_rows,
#                     "processedRows": imported_rows,
#                     "failedRows": failed_rows,
#                     "success": file_result["success"],
#                 }
#
#                 if not file_result["success"]:
#                     # 收集错误信息
#                     errors = []
#                     for sheet_name, sheet_result in file_result["sheets"].items():
#                         if not sheet_result["success"] and sheet_result["errors"]:
#                             errors.extend(sheet_result["errors"])
#
#                     file_info["error"] = "; ".join(errors) if errors else "导入失败"
#                     all_results["success"] = False
#
#                 all_results["files"].append(file_info)
#                 all_results["totalRows"] += processed_rows
#                 all_results["processedRows"] += imported_rows
#                 all_results["failedRows"] += failed_rows
#
#             except Exception as e:
#                 logger.error(f"处理文件 {file.filename} 时发生错误: {str(e)}")
#                 all_results["files"].append({
#                     "fileName": file.filename,
#                     "totalRows": 0,
#                     "processedRows": 0,
#                     "failedRows": 0,
#                     "success": False,
#                     "error": str(e)
#                 })
#                 all_results["success"] = False
#
#         # 将所有表结构信息添加到结果中（用于新的dbInfo结构）
#         inspector = inspect(connector._engine)
#         for table_name in processed_tables:
#             columns = inspector.get_columns(table_name)
#             table_info = {
#                 "tableName": table_name,
#                 "columns": [
#                     {
#                         "name": col["name"],
#                         "type": str(col["type"]),
#                         "nullable": col.get("nullable", True)
#                     }
#                     for col in columns
#                 ]
#             }
#             all_results["dbInfo"]["tables"].append(table_info)
#
#         # 将解析的表结构信息添加到结果中
#         # all_results["tableData"] = table_data
#         return Result.succ(all_results)
#
#     except Exception as e:
#         logger.error(f"处理Excel文件时发生错误: {str(e)}")
#         return Result.failed(code="E0006", msg=f"处理Excel文件时发生错误: {str(e)}")
#     finally:
#         # 清理临时文件
#         shutil.rmtree(temp_dir, ignore_errors=True)

@router.post("/v1/resource/file/read")
async def file_read(
    conv_uid: str,
    file_key: str,
    user_name: Optional[str] = None,
    sys_code: Optional[str] = None,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(f"file_read:{conv_uid},{file_key}")
    file_client = FileClient()
    res = await file_client.read_file(conv_uid=conv_uid, file_key=file_key)
    df = pd.read_excel(res, index_col=False)
    return Result.succ(df.to_json(orient="records", date_format="iso", date_unit="s"))


def get_hist_messages(conv_uid: str, user_name: str = None):
    from dbgpt_serve.conversation.service.service import Service as ConversationService

    instance: ConversationService = ConversationService.get_instance(CFG.SYSTEM_APP)
    return instance.get_history_messages({"conv_uid": conv_uid, "user_name": user_name})


async def get_chat_instance(dialogue: ConversationVo = Body()) -> BaseChat:
    logger.info(f"get_chat_instance:{dialogue}")
    if not dialogue.chat_mode:
        dialogue.chat_mode = ChatScene.ChatNormal.value()
    if not dialogue.conv_uid:
        conv_vo = __new_conversation(
            dialogue.chat_mode, dialogue.user_name, dialogue.sys_code
        )
        dialogue.conv_uid = conv_vo.conv_uid

    if not ChatScene.is_valid_mode(dialogue.chat_mode):
        raise StopAsyncIteration(
            Result.failed("Unsupported Chat Mode," + dialogue.chat_mode + "!")
        )

    chat_param = ChatParam(
        chat_session_id=dialogue.conv_uid,
        user_name=dialogue.user_name,
        sys_code=dialogue.sys_code,
        current_user_input=dialogue.user_input,
        select_param=dialogue.select_param,
        model_name=dialogue.model_name,
        app_code=dialogue.app_code,
        ext_info=dialogue.ext_info,
        temperature=dialogue.temperature,
        max_new_tokens=dialogue.max_new_tokens,
        prompt_code=dialogue.prompt_code,
        chat_mode=ChatScene.of_mode(dialogue.chat_mode),
    )
    chat: BaseChat = await blocking_func_to_async(
        CFG.SYSTEM_APP,
        CHAT_FACTORY.get_implementation,
        dialogue.chat_mode,
        CFG.SYSTEM_APP,
        **{"chat_param": chat_param},
    )
    return chat


@router.post("/v1/chat/prepare")
async def chat_prepare(
    dialogue: ConversationVo = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(json.dumps(dialogue.__dict__))
    # dialogue.model_name = CFG.LLM_MODEL
    dialogue.user_name = user_token.user_id if user_token else dialogue.user_name
    logger.info(f"chat_prepare:{dialogue}")
    ## check conv_uid
    chat: BaseChat = await get_chat_instance(dialogue)

    await chat.prepare()

    # Refresh messages
    return Result.succ(get_hist_messages(dialogue.conv_uid, user_token.user_id))


@router.post("/v1/chat/completions")
async def chat_completions(
    dialogue: ConversationVo = Body(),
    flow_service: FlowService = Depends(get_chat_flow),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(
        f"chat_completions:{dialogue.chat_mode},{dialogue.select_param},"
        f"{dialogue.model_name}, timestamp={int(time.time() * 1000)}"
    )
    dialogue.user_name = user_token.user_id if user_token else dialogue.user_name
    dialogue = adapt_native_app_model(dialogue)
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    try:
        domain_type = _parse_domain_type(dialogue)
        if dialogue.chat_mode == ChatScene.ChatAgent.value():
            from dbgpt_serve.agent.agents.controller import multi_agents

            dialogue.ext_info.update({"model_name": dialogue.model_name})
            dialogue.ext_info.update({"incremental": dialogue.incremental})
            dialogue.ext_info.update({"temperature": dialogue.temperature})
            return StreamingResponse(
                multi_agents.app_agent_chat(
                    conv_uid=dialogue.conv_uid,
                    chat_mode=dialogue.chat_mode,
                    gpts_name=dialogue.app_code,
                    user_query=dialogue.user_input,
                    user_code=dialogue.user_name,
                    sys_code=dialogue.sys_code,
                    **dialogue.ext_info,
                ),
                headers=headers,
                media_type="text/event-stream",
            )
        elif dialogue.chat_mode == ChatScene.ChatFlow.value():
            flow_req = CommonLLMHttpRequestBody(
                model=dialogue.model_name,
                messages=dialogue.user_input,
                stream=True,
                # context=flow_ctx,
                # temperature=
                # max_new_tokens=
                # enable_vis=
                conv_uid=dialogue.conv_uid,
                span_id=root_tracer.get_current_span_id(),
                chat_mode=dialogue.chat_mode,
                chat_param=dialogue.select_param,
                user_name=dialogue.user_name,
                sys_code=dialogue.sys_code,
                incremental=dialogue.incremental,
            )
            return StreamingResponse(
                flow_service.chat_stream_flow_str(dialogue.select_param, flow_req),
                headers=headers,
                media_type="text/event-stream",
            )
        elif domain_type is not None and domain_type != "Normal":
            return StreamingResponse(
                chat_with_domain_flow(dialogue, domain_type),
                headers=headers,
                media_type="text/event-stream",
            )

        else:
            with root_tracer.start_span(
                "get_chat_instance", span_type=SpanType.CHAT, metadata=dialogue.dict()
            ):
                chat: BaseChat = await get_chat_instance(dialogue)

            if not chat.prompt_template.stream_out:
                return StreamingResponse(
                    no_stream_generator(chat),
                    headers=headers,
                    media_type="text/event-stream",
                )
            else:
                return StreamingResponse(
                    stream_generator(
                        chat,
                        dialogue.incremental,
                        dialogue.model_name,
                        openai_format=dialogue.incremental,
                    ),
                    headers=headers,
                    media_type="text/plain",
                )
    except Exception as e:
        logger.exception(f"Chat Exception!{dialogue}", e)

        async def error_text(err_msg):
            yield f"data:{err_msg}\n\n"

        return StreamingResponse(
            error_text(str(e)),
            headers=headers,
            media_type="text/plain",
        )
    finally:
        # write to recent usage app.
        if dialogue.user_name is not None and dialogue.app_code is not None:
            user_recent_app_dao.upsert(
                user_code=dialogue.user_name,
                sys_code=dialogue.sys_code,
                app_code=dialogue.app_code,
            )


@router.post("/v1/chat/topic/terminate")
async def terminate_topic(
    conv_id: str,
    round_index: int,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(f"terminate_topic:{conv_id},{round_index}")
    try:
        from dbgpt_serve.agent.agents.controller import multi_agents

        return Result.succ(await multi_agents.topic_terminate(conv_id))
    except Exception as e:
        logger.exception("Topic terminate error!")
        return Result.failed(code="E0102", msg=str(e))


@router.get("/v1/model/types")
async def model_types(controller: BaseModelController = Depends(get_model_controller)):
    logger.info("/controller/model/types")
    try:
        types = set()
        models = await controller.get_all_instances(healthy_only=True)
        for model in models:
            worker_name, worker_type = model.model_name.split("@")
            if worker_type == "llm" and worker_name not in [
                "codegpt_proxyllm",
                "text2sql_proxyllm",
            ]:
                types.add(worker_name)
        return Result.succ(list(types))

    except Exception as e:
        return Result.failed(code="E000X", msg=f"controller model types error {e}")


@router.get("/v1/test")
async def test():
    return "service status is UP"


@router.get(
    "/v1/model/supports",
    deprecated=True,
    description="This endpoint is deprecated. Please use "
    "`/api/v2/serve/model/model-types` instead. It will be removed in v0.8.0.",
)
async def model_supports(worker_manager: WorkerManager = Depends(get_worker_manager)):
    logger.warning(
        "The endpoint `/api/v1/model/supports` is deprecated. Please use "
        "`/api/v2/serve/model/model-types` instead. It will be removed in v0.8.0."
    )
    try:
        models = await worker_manager.supported_models()
        return Result.succ(FlatSupportedModel.from_supports(models))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"Fetch supportd models error {e}")


async def flow_stream_generator(func, incremental: bool, model_name: str):
    stream_id = f"chatcmpl-{str(uuid.uuid1())}"
    previous_response = ""
    async for chunk in func:
        if chunk:
            msg = chunk.replace("\ufffd", "")
            if incremental:
                incremental_output = msg[len(previous_response) :]
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=incremental_output),
                )
                chunk = ChatCompletionStreamResponse(
                    id=stream_id, choices=[choice_data], model=model_name
                )
                _content = json.dumps(
                    chunk.dict(exclude_unset=True), ensure_ascii=False
                )
                yield f"data: {_content}\n\n"
            else:
                # TODO generate an openai-compatible streaming responses
                msg = msg.replace("\n", "\\n")
                yield f"data:{msg}\n\n"
            previous_response = msg
    if incremental:
        yield "data: [DONE]\n\n"


async def no_stream_generator(chat):
    with root_tracer.start_span("no_stream_generator"):
        msg = await chat.nostream_call()
        yield f"data: {msg}\n\n"


async def stream_generator(
    chat,
    incremental: bool,
    model_name: str,
    text_output: bool = True,
    openai_format: bool = False,
    conv_uid: str = None,
):
    """Generate streaming responses

    Our goal is to generate an openai-compatible streaming responses.
    Currently, the incremental response is compatible, and the full response will be
    transformed in the future.

    Args:
        chat (BaseChat): Chat instance.
        incremental (bool): Used to control whether the content is returned
            incrementally or in full each time.
        model_name (str): The model name

    Yields:
        _type_: streaming responses
    """
    span = root_tracer.start_span("stream_generator")
    msg = "[LLM_ERROR]: llm server has no output, maybe your prompt template is wrong."

    stream_id = conv_uid or f"chatcmpl-{str(uuid.uuid1())}"
    try:
        if incremental and not openai_format:
            raise ValueError("Incremental response must be openai-compatible format.")
        async for chunk in chat.stream_call(
            text_output=text_output, incremental=incremental
        ):
            if not chunk:
                await asyncio.sleep(0.02)
                continue

            if openai_format:
                # Must be ModelOutput
                output: ModelOutput = cast(ModelOutput, chunk)
                text = None
                think_text = None
                if output.has_text:
                    text = output.text
                if output.has_thinking:
                    think_text = output.thinking_text
                if incremental:
                    choice_data = ChatCompletionResponseStreamChoice(
                        index=0,
                        delta=DeltaMessage(
                            role="assistant", content=text, reasoning_content=think_text
                        ),
                    )
                    chunk = ChatCompletionStreamResponse(
                        id=stream_id, choices=[choice_data], model=model_name
                    )
                    _content = json.dumps(
                        chunk.dict(exclude_unset=True), ensure_ascii=False
                    )
                    yield f"data: {_content}\n\n"
                else:
                    choice_data = ChatCompletionResponseChoice(
                        index=0,
                        message=ChatMessage(
                            role="assistant",
                            content=output.text,
                            reasoning_content=output.thinking_text,
                        ),
                    )
                    if output.usage:
                        usage = UsageInfo(**output.usage)
                    else:
                        usage = UsageInfo()
                    _content = ChatCompletionResponse(
                        id=stream_id,
                        choices=[choice_data],
                        model=model_name,
                        usage=usage,
                    )
                    _content = json.dumps(
                        chunk.dict(exclude_unset=True), ensure_ascii=False
                    )
                    yield f"data: {_content}\n\n"
            else:
                msg = chunk.replace("\ufffd", "")
                msg = msg.replace("\n", "\\n")
                yield f"data:{msg}\n\n"
            await asyncio.sleep(0.02)
        if incremental:
            yield "data: [DONE]\n\n"
        span.end()
    except Exception as e:
        logger.exception("stream_generator error")
        yield f"data: [SERVER_ERROR]{str(e)}\n\n"
        if incremental:
            yield "data: [DONE]\n\n"


def message2Vo(message: dict, order, model_name) -> MessageVo:
    return MessageVo(
        role=message["type"],
        context=message["data"]["content"],
        order=order,
        model_name=model_name,
    )


def _parse_domain_type(dialogue: ConversationVo) -> Optional[str]:
    if dialogue.chat_mode == ChatScene.ChatKnowledge.value():
        # Supported in the knowledge chat
        if dialogue.app_code == "" or dialogue.app_code == "chat_knowledge":
            spaces = knowledge_service.get_knowledge_space(
                KnowledgeSpaceRequest(name=dialogue.select_param)
            )
        else:
            spaces = knowledge_service.get_knowledge_space(
                KnowledgeSpaceRequest(name=dialogue.select_param)
            )
        if len(spaces) == 0:
            raise ValueError(f"Knowledge space {dialogue.select_param} not found")
        dialogue.select_param = spaces[0].name
        if spaces[0].domain_type:
            return spaces[0].domain_type
    else:
        return None


async def chat_with_domain_flow(dialogue: ConversationVo, domain_type: str):
    """Chat with domain flow"""
    dag_manager = get_dag_manager()
    dags = dag_manager.get_dags_by_tag(TAG_KEY_KNOWLEDGE_CHAT_DOMAIN_TYPE, domain_type)
    if not dags or not dags[0].leaf_nodes:
        raise ValueError(f"Cant find the DAG for domain type {domain_type}")

    end_task = cast(BaseOperator, dags[0].leaf_nodes[0])
    space = dialogue.select_param
    connector_manager = CFG.local_db_manager
    # TODO: Some flow maybe not connector
    db_list = [item["db_name"] for item in connector_manager.get_db_list()]
    db_names = [item for item in db_list if space in item]
    if len(db_names) == 0:
        raise ValueError(f"fin repost dbname {space}_fin_report not found.")
    flow_ctx = {"space": space, "db_name": db_names[0]}
    request = CommonLLMHttpRequestBody(
        model=dialogue.model_name,
        messages=dialogue.user_input,
        stream=True,
        extra=flow_ctx,
        conv_uid=dialogue.conv_uid,
        span_id=root_tracer.get_current_span_id(),
        chat_mode=dialogue.chat_mode,
        chat_param=dialogue.select_param,
        user_name=dialogue.user_name,
        sys_code=dialogue.sys_code,
        incremental=dialogue.incremental,
    )
    async for output in safe_chat_stream_with_dag_task(end_task, request, False):
        text = output.gen_text_with_thinking()
        if text:
            text = text.replace("\n", "\\n")
        if output.error_code != 0:
            yield f"data:[SERVER_ERROR]{text}\n\n"
            break
        else:
            yield f"data:{text}\n\n"
