import json
import logging
import shutil
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Optional

from fastapi.responses import FileResponse
# 初始化FunASR转写器
from fastapi import APIRouter
from fastapi import Query, Form, File, UploadFile, BackgroundTasks
from fastapi.params import Depends
from sqlalchemy import inspect
from voice2text.tran.schema.dto import ApiResponse, VoicePrintInfo
from voice2text.tran.schema.prints import SampleInfo

from dbgpt.core.interface.file import FileStorageClient
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt_app.expend.dependencies import get_speech2text_service
from dbgpt_app.expend.excel2db import ExtendedMySQLConnector, ExcelToMysql
from dbgpt_app.expend.service.speech2text import Speech2TextService
from dbgpt_app.knowledge.api import get_fs
from dbgpt_app.openapi.api_view_model import (
    Result,
)

# from voice2text.tran.funasr_transcriber import Speech2TextService

# 导入我们的FunASR转写服务

#
# transcriber = Speech2TextService(
#     device="cpu",
#     funasr_model="paraformer-zh",
#     funasr_model_revision="v2.0.4",
#     vad_model="fsmn-vad",
#     vad_model_revision="v2.0.4",
#     punc_model="ct-punc",
#     punc_model_revision="v2.0.4",
#     spk_model="cam++",
#     spk_model_revision="v2.0.2"
# )
# transcriber = None
router = APIRouter()
logger = logging.getLogger(__name__)
@router.post("/v1/expand/dataprocess/excel2db")
async def excel2db(
        # 通过Query从URL中获取的参数
        dbType: str = Query(..., description="数据库类型"),
        dbHost: str = Query(..., description="数据库主机"),
        dbPort: int = Query(3306, description="数据库端口"),
        dbName: str = Query(..., description="数据库名称"),
        dbUser: str = Query(..., description="数据库用户名"),
        autoCreate: str = Query(..., description="是否自动创建库或表"),
        chunkSize: str = Query(..., description="数据块大小"),
        ifExists: str = Query(..., description="如果已存在的处理方式"),

        # 可选的Query参数
        sheetNames: Optional[str] = Query(None, description="工作表名称，多个用逗号分隔"),
        tablePrefix: Optional[str] = Query(None, description="表前缀"),
        tableMapping: Optional[str] = Query(None, description="表映射关系"),
        columnMapping: Optional[str] = Query(None, description="列映射关系"),

        # 通过Form从请求体中获取的敏感参数
        dbPassword: str = Form(..., description="数据库密码"),

        # 文件上传
        files: List[UploadFile] = File(..., description="Excel文件")
):
    """
    处理Excel文件并导入到数据库

    - 从URL查询参数中获取大部分配置信息
    - 从表单数据中获取敏感信息（如密码）
    - 处理上传的Excel文件并将其导入到MySQL数据库
    """
    logger.info(f"处理Excel到数据库导入：{dbType}, {dbHost}:{dbPort}, {dbName}")

    # 转换字符串参数为相应的类型
    chunk_size = int(chunkSize)
    auto_create = autoCreate.lower() in ('是', 'yes', 'true', '1')

    # 解析可选参数
    sheet_names_list = None
    if sheetNames:
        sheet_names_list = [s.strip() for s in sheetNames.split(',')]

    table_mapping_dict = None
    if tableMapping:
        try:
            table_mapping_dict = json.loads(tableMapping)
        except json.JSONDecodeError:
            return {
                "success": False,
                "err_code": "E0002",
                "err_msg": "表映射JSON格式错误",
                "data": None
            }

    column_mapping_dict = None
    if columnMapping:
        try:
            column_mapping_dict = json.loads(columnMapping)
        except json.JSONDecodeError:
            return Result.failed(code="E0003", msg="列映射JSON格式错误")

    # 验证其他参数
    if ifExists not in ['fail', 'replace', 'append']:
        return Result.failed(code="E0005", msg="ifExists必须是'fail'、'replace'或'append'之一")

    # 创建一个临时目录来存储上传的文件
    temp_dir = tempfile.mkdtemp()
    try:
        # 处理上传的所有文件
        all_results = {
            "files": [],
            "success": True,
            "fileCount": len(files),
            "totalRows": 0,
            "processedRows": 0,
            "failedRows": 0,
            "dbInfo": {
                "dbName": dbName,
                "tables": []  # 用于存储表名和结构信息
            }
        }

        # # 用于临时存储表字段映射信息
        # table_data = []

        # 创建MySQL连接器
        try:
            connector = ExtendedMySQLConnector.from_uri_db(
                host=dbHost,
                port=dbPort,
                user=dbUser,
                pwd=dbPassword,
                db_name=dbName,
                auto_create=auto_create
            )
        except Exception as e:
            logger.error(f"数据库连接错误: {str(e)}")
            return Result.failed(code="E0005", msg=f"数据库连接错误: {str(e)}")

        # 用于存储所有处理过的表信息
        processed_tables = set()

        for file in files:
            # 将上传的文件保存到临时目录
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 创建Excel导入器并处理文件
            try:
                importer = ExcelToMysql.from_connector(
                    connector=connector,
                    excel_path_buffer=file_path,
                    auto_create=auto_create,
                    sheet_names=sheet_names_list,
                    table_prefix=tablePrefix or "",
                    table_mapping=table_mapping_dict,
                    chunk_size=chunk_size,
                    if_exists=ifExists,
                    column_mapping=column_mapping_dict
                )

                # 导入Excel文件
                file_result = importer.import_excel()

                # 收集处理过的表信息
                for sheet_name, sheet_result in file_result["sheets"].items():
                    if sheet_result["success"]:
                        table_name = importer._get_table_name(sheet_name)
                        processed_tables.add(table_name)

                # 计算总计数据
                processed_rows = sum(sheet["rows_processed"] for sheet in file_result["sheets"].values())
                imported_rows = sum(sheet["rows_imported"] for sheet in file_result["sheets"].values())
                failed_rows = processed_rows - imported_rows

                # 添加到结果集
                file_info = {
                    "fileName": file.filename,
                    "bucket": "local",
                    "totalRows": processed_rows,
                    "processedRows": imported_rows,
                    "failedRows": failed_rows,
                    "success": file_result["success"],
                }

                if not file_result["success"]:
                    # 收集错误信息
                    errors = []
                    for sheet_name, sheet_result in file_result["sheets"].items():
                        if not sheet_result["success"] and sheet_result["errors"]:
                            errors.extend(sheet_result["errors"])

                    file_info["error"] = "; ".join(errors) if errors else "导入失败"
                    all_results["success"] = False

                all_results["files"].append(file_info)
                all_results["totalRows"] += processed_rows
                all_results["processedRows"] += imported_rows
                all_results["failedRows"] += failed_rows

            except Exception as e:
                logger.error(f"处理文件 {file.filename} 时发生错误: {str(e)}")
                all_results["files"].append({
                    "fileName": file.filename,
                    "totalRows": 0,
                    "processedRows": 0,
                    "failedRows": 0,
                    "success": False,
                    "error": str(e)
                })
                all_results["success"] = False

        # 将所有表结构信息添加到结果中（用于新的dbInfo结构）
        inspector = inspect(connector._engine)
        for table_name in processed_tables:
            columns = inspector.get_columns(table_name)
            table_info = {
                "tableName": table_name,
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True)
                    }
                    for col in columns
                ]
            }
            all_results["dbInfo"]["tables"].append(table_info)

        # 将解析的表结构信息添加到结果中
        # all_results["tableData"] = table_data
        return Result.succ(all_results)

    except Exception as e:
        logger.error(f"处理Excel文件时发生错误: {str(e)}")
        return Result.failed(code="E0006", msg=f"处理Excel文件时发生错误: {str(e)}")
    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


# 语音转文字API
from voice2text.tran.server import parse_filename


# 语音转文字API
@router.post("/v1/expand/voiceprocess/voice2text")
async def voice2text(
        # 通过Query从URL中获取的参数
        language: str = Query("auto", description="识别语言"),
        model: str = Query("default", description="识别模型"),
        enablePunctuation: str = Query("true", description="是否启用标点符号"),
        speakerDiarization: str = Query("true", description="是否启用说话人分离"),
        # 文件上传
        files: List[UploadFile] = File(..., description="音频文件"),
        auto_register: Optional[bool] = Query(True, description="是否将未知声音自动注册为声纹"),
        threshold: Optional[float] = Query(0.5, description="声纹匹配阈值"),
        hotword: Optional[str] = Query("", description="热词"),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        transcriber: Speech2TextService = Depends(get_speech2text_service)
):
    """
    语音转文字处理API
    接收多个音频文件，返回处理结果
    """
    if not files:
        return Result.failed(code="E0101", msg="请上传至少一个音频文件")

    # 创建一个临时目录存储上传的文件
    temp_dir = tempfile.mkdtemp()

    try:
        # 配置参数
        enable_punctuation = enablePunctuation.lower() == "true"
        enable_speaker_diarization = speakerDiarization.lower() == "true"

        # 如果没有启用说话人分离，将auto_register设为False
        if not enable_speaker_diarization:
            auto_register = False

        results = []
        fileCount = len(files)
        processedFiles = 0
        failedFiles = 0
        totalDuration = 0

        # 存储自动注册的声纹信息
        auto_registered_speakers_info = {}

        # 处理每个文件
        for file in files:
            file_uid = str(uuid.uuid4())
            file_path = os.path.join(temp_dir, f"{file_uid}_{file.filename}")

            try:
                # 保存上传的文件
                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)

                # 尝试从文件名解析位置和时间信息
                location, date, record_time = parse_filename(file.filename)

                # 使用FunASR转写服务处理文件
                process_start_time = time.time()

                # 异步调用转写函数
                transcription_result = await transcriber.transcribe_file(audio_file_path=file_path,
                                                        language=language,
                                                        hotword=hotword,
                                                       threshold=threshold,
                                                       auto_register_unknown=auto_register,
                                                       file_location=location,
                                                       file_date=date,
                                                       file_time=record_time)

                # 提取结果
                text = transcription_result["transcript"]
                duration = transcription_result["audio_duration"]
                output_file = transcription_result.get("output_file", "")

                # 收集自动注册的声纹信息
                if transcription_result.get("auto_registered_speakers"):
                    auto_registered_speakers_info[file.filename] = {
                        "speakers": transcription_result["auto_registered_speakers"],
                        "audio_samples": transcription_result.get("voiceprint_audio_samples", {})
                    }

                totalDuration += duration

                process_end_time = time.time()
                processing_time = process_end_time - process_start_time

                # 添加到结果列表
                file_result = {
                    "fileUid": file_uid,
                    "fileName": file.filename,
                    "text": text,
                    "processingTime": round(processing_time, 2),
                    "success": True,
                    "duration": round(duration, 2),
                    "outputFile": os.path.basename(output_file) if output_file else ""
                }

                # 如果有自动注册的声纹，添加到结果中
                if file.filename in auto_registered_speakers_info:
                    file_result["autoRegisteredSpeakers"] = len(
                        auto_registered_speakers_info[file.filename]["speakers"])

                results.append(file_result)
                processedFiles += 1

            except Exception as e:
                logger.error(f"处理文件 {file.filename} 时发生错误: {str(e)}")
                failedFiles += 1
                results.append({
                    "fileUid": file_uid,
                    "fileName": file.filename,
                    "text": "",
                    "processingTime": 0,
                    "success": False,
                    "error": str(e)
                })

        # 构建结果数据
        result_data = {
            "fileCount": fileCount,
            "totalDuration": round(totalDuration),
            "processedFiles": processedFiles,
            "failedFiles": failedFiles,
            "files": results
        }

        # 如果有自动注册的声纹，添加到结果中
        if auto_registered_speakers_info:
            total_auto_registered = sum(len(info["speakers"]) for info in auto_registered_speakers_info.values())
            if total_auto_registered > 0:
                result_data["autoRegisteredSpeakers"] = total_auto_registered
                # 收集所有自动注册的声纹ID
                result_data["autoRegisteredSpeakerIds"] = []
                for file_info in auto_registered_speakers_info.values():
                    result_data["autoRegisteredSpeakerIds"].extend(list(file_info["speakers"].keys()))

        # 根据处理结果返回成功或失败
        if failedFiles == 0:
            return Result.succ(result_data)
        elif processedFiles > 0:
            # 部分成功，仍然返回成功但带有处理信息
            return Result.succ(result_data)
        else:
            # 全部失败
            return Result.failed(
                code="E0102",
                msg="所有音频文件处理失败",
                data=result_data
            )

    except Exception as e:
        logger.error(f"处理语音转文字时发生错误: {str(e)}")
        return Result.failed(code="E0103", msg=f"处理语音转文字时发生错误: {str(e)}")

    finally:
        # 清理临时文件
        def cleanup():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}")

        background_tasks.add_task(cleanup)



@router.get("/v1/expand/voiceprofile/sample/{sample_id}")
async def get_voice_sample(sample_id: str, transcriber: Speech2TextService = Depends(get_speech2text_service)):
    """
    获取声纹样本文件
    """
    try:
        # 从样本ID获取文件路径
        file_id = sample_id.split(":")[-1]  # 只取最后一部分作为文件ID
        tmp_path = tempfile.gettempdir() + f"{file_id}.wav"
        success = await transcriber.download_file(file_id=file_id, file_path=tmp_path)

        if not success:
            raise HTTPException(status_code=404, detail="样本文件不存在")

        # 确保指针在开始位置
        # sample_data.seek(0)

        return FileResponse(tmp_path, media_type="audio/wav")

    except Exception as e:
        logger.error(f"获取声纹样本失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取声纹样本失败: {str(e)}")


def make_profile(samples: List[VoicePrintInfo]):
    profiles = []
    for voice_print in samples:
        # 生成声纹档案数据
        sample_list = voice_print.sample_list
        final_samples = []
        for sample in sample_list:
            final_samples.append({
                "id": f"{sample.speaker_id}:{sample.audio_file_id}",
                "name": sample.filename,
                "duration": sample.audio_duration,
                "uploadDate": sample.created_at,
                "url": f"/v1/expand/voiceprofile/sample/{sample.audio_file_id}"
            })
        profile_data = {
            "id": voice_print.speaker_id,  # 使用声纹ID作为标识
            "name": voice_print.speaker_id,
            "type": "named" if voice_print.named else "unnamed",
            "samples": final_samples,
            "sampleCount": len(voice_print.sample_list)
        }
        profiles.append(profile_data)
    return profiles

# 获取所有声纹档案
@router.get("/v1/expand/voiceprofile/list")
async def list_voice_profiles(include_unnamed: bool = Query(True, description="是否包含未命名声纹"), transcriber: Speech2TextService = Depends(get_speech2text_service)):
    """
    获取所有声纹档案
    """
    try:
        # 获取声纹数据
        voice_print_data: ApiResponse[List[VoicePrintInfo]] = await transcriber.list_registered_voices(include_unnamed=include_unnamed)

        # 获取所有声纹样本路径
        if not voice_print_data.success:
            return Result.failed(code="E0202", msg="获取声纹数据失败")

        # 格式化为前端所需的数据结构
        profiles = make_profile(voice_print_data.data)

        return Result.succ({"profiles": profiles})

    except Exception as e:
        logger.error(f"获取声纹列表失败: {str(e)}")
        return Result.failed(code="E0201", msg=f"获取声纹列表失败: {str(e)}")


# 创建新声纹档案
@router.post("/v1/expand/voiceprofile/create")
async def create_voice_profile(
        name: str = Form(..., description="声纹名称"),
        file: Optional[UploadFile] = File(None, description="音频文件（可选）"),
        transcriber: Speech2TextService = Depends(get_speech2text_service)
):
    """
    创建新声纹档案
    可以选择上传音频样本文件
    """
    temp_dir = None
    if file:
        temp_dir = tempfile.mkdtemp()

    try:
        if file:
            # 保存上传的文件
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # 注册声纹
            result = await transcriber.register_voice(name, file_path)
            voice_print_data: ApiResponse[List[VoicePrintInfo]] = await transcriber.list_registered_voices(
                include_unnamed=True)

            # 获取所有声纹样本路径
            if not voice_print_data.success:
                return Result.failed(code="E0301", msg="获取声纹数据失败")

            # 格式化为前端所需的数据结构
            profiles = make_profile(voice_print_data.data)
            return Result.succ(profiles)
        else:
            Result.failed(code="E0301", msg=f"未提供音频文件，无法创建声纹档案")

    except Exception as e:
        logger.error(f"创建声纹失败: {str(e)}")
        return Result.failed(code="E0301", msg=f"创建声纹失败: {str(e)}")

    finally:
        if temp_dir:
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}")


# 更新声纹档案名称
@router.post("/v1/expand/voiceprofile/update")
async def update_voice_profile(
        id: str = Form(..., description="声纹ID"),
        name: str = Form(..., description="新声纹名称"),
        transcriber: Speech2TextService = Depends(get_speech2text_service)
):
    """
    更新声纹档案名称
    """
    try:
        # 调用声纹重命名方法
        success = await transcriber.rename_voice_print(id, name)

        if not success:

            return Result.failed(code="E0402", msg=f"更新声纹名称失败，目标名称可能已存在或原声纹不存在")

        # 获取更新后的声纹样本信息
        voice_print_data: ApiResponse[List[VoicePrintInfo]] = await transcriber.list_registered_voices(
            include_unnamed=True)

        # 获取所有声纹样本路径
        if not voice_print_data.success:
            return Result.failed(code="E0301", msg="获取声纹数据失败")
        return Result.succ(success)

    except Exception as e:
        logger.error(f"更新声纹名称失败: {str(e)}")
        return Result.failed(code="E0401", msg=f"更新声纹名称失败: {str(e)}")


# 删除声纹档案
@router.post("/v1/expand/voiceprofile/delete")
async def delete_voice_profile(id: str = Form(..., description="声纹ID"), transcriber: Speech2TextService = Depends(get_speech2text_service)):
    """
    删除声纹档案
    """
    try:
        # 获取声纹目录路径
        speaker_id = id.split(":")[0]  # 只取最后一部分作为声纹ID
        success = await transcriber.delete_speaker(speaker_id)
        if not success:
            return Result.failed(code="E0502", msg=f"删除声纹失败，声纹ID '{id}' 可能不存在")

        return Result.succ({"success": True, "message": f"声纹 '{id}' 已成功删除"})

    except Exception as e:
        logger.error(f"删除声纹失败: {str(e)}")
        return Result.failed(code="E0501", msg=f"删除声纹失败: {str(e)}")


# 添加声纹样本
@router.post("/v1/expand/voiceprofile/addsample")
async def add_voice_sample(
        profileId: str = Form(..., description="声纹ID"),
        file: UploadFile = File(..., description="音频文件"),
        transcriber: Speech2TextService = Depends(get_speech2text_service)
):
    """
    添加声纹样本
    """
    # 创建一个临时目录存储上传的文件
    temp_dir = tempfile.mkdtemp()

    try:
        # 保存上传的文件
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 调用声纹管理器添加样本
        sample_id = transcriber.voice_print_manager.add_sample(profileId, file_path)

        if not sample_id:
            return Result.failed(code="E0602", msg=f"添加声纹样本失败，声纹ID '{profileId}' 可能不存在")

        # 获取样本文件路径
        sample_path = transcriber.voice_print_manager.get_sample_path_by_id(sample_id)

        if not sample_path or not os.path.exists(sample_path):
            return Result.failed(code="E0603", msg=f"添加声纹样本成功，但无法获取样本文件信息")

        # 获取文件大小和修改时间
        file_stats = os.stat(sample_path)
        file_size = file_stats.st_size
        mod_time = datetime.fromtimestamp(file_stats.st_mtime)

        # 计算音频时长（估计值）
        duration_sec = file_size / 32000
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)

        # 返回样本信息
        sample_data = {
            "id": sample_id,
            "name": os.path.basename(sample_path),
            "duration": f"{minutes}:{seconds:02d}",
            "uploadDate": mod_time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": f"/v1/expand/voiceprofile/sample/{sample_id}",
            "profileId": profileId
        }

        return Result.succ(sample_data)

    except Exception as e:
        logger.error(f"添加声纹样本失败: {str(e)}")
        return Result.failed(code="E0601", msg=f"添加声纹样本失败: {str(e)}")

    finally:
        # 清理临时文件
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"清理临时文件失败: {str(e)}")


# 删除声纹样本
@router.post("/v1/expand/voiceprofile/deletesample")
async def delete_voice_sample(
        sampleId: str = Form(..., description="样本ID"),
        transcriber: Speech2TextService = Depends(get_speech2text_service)
):
    """
    删除声纹样本
    """
    try:
        # 调用声纹管理器删除样本
        speaker_id, audio_file_id = sampleId.split(":")
        success = await transcriber.delete_audio_sample(speaker_id, audio_file_id)

        if not success:
            return Result.failed(code="E0702", msg=f"删除声纹样本失败，样本ID '{sampleId}' 可能不存在")

        return Result.succ({
            "success": True,
            "message": f"样本 '{sampleId}' 已成功删除"
        })

    except Exception as e:
        logger.error(f"删除声纹样本失败: {str(e)}")
        return Result.failed(code="E0701", msg=f"删除声纹样本失败: {str(e)}")


# 清空所有声纹
@router.post("/v1/expand/voiceprofile/clear")
async def clear_voice_profiles(transcriber: Speech2TextService = Depends(get_speech2text_service)):
    """
    清空所有声纹数据
    """
    try:
        voice_print_data: ApiResponse[List[VoicePrintInfo]] = await transcriber.list_registered_voices()
        if not voice_print_data.success:
            return Result.failed(code="E0802", msg="获取声纹数据失败，无法清空")
        for voice_print in voice_print_data.data:
            speaker_id = voice_print.speaker_id
            await transcriber.delete_speaker(speaker_id)


        return Result.succ({
            "success": True,
            "message": "所有声纹数据已成功清空"
        })

    except Exception as e:
        logger.error(f"清空声纹数据失败: {str(e)}")
        return Result.failed(code="E0801", msg=f"清空声纹数据失败: {str(e)}")


# 批量注册声纹
@router.post("/v1/expand/voiceprofile/batchregister")
async def batch_register_voice_profiles(
        directory: str = Form(..., description="包含音频文件的目录路径"),
        transcriber: Speech2TextService = Depends(get_speech2text_service)
):
    """
    从目录批量注册声纹
    """
    try:
        # 调用声纹管理器从目录注册声纹
        registered_voices = transcriber.register_voices_from_directory(directory)

        if not registered_voices:
            return Result.failed(code="E0901", msg=f"目录 '{directory}' 中没有找到有效的音频文件")

        return Result.succ({
            "success": True,
            "message": f"成功从目录注册了 {len(registered_voices)} 个声纹",
            "registeredVoices": registered_voices
        })

    except Exception as e:
        logger.error(f"批量注册声纹失败: {str(e)}")
        return Result.failed(code="E0901", msg=f"批量注册声纹失败: {str(e)}")


from fastapi import HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
import os
import urllib.parse
from typing import AsyncGenerator
import mimetypes

import urllib.parse
from pathlib import Path



def build_download_headers(file_name: str, file_size: int = 0) -> dict:
    """
    构建下载响应头，确保文件名正确传递
    """
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Accept-Ranges": "bytes"
    }

    # 处理文件名编码
    try:
        # 尝试使用 ASCII 编码（最兼容）
        file_name.encode('ascii')
        # 如果是纯 ASCII，使用简单格式
        headers["Content-Disposition"] = f'attachment; filename="{file_name}"'
    except UnicodeEncodeError:
        # 如果包含非 ASCII 字符，使用 RFC 5987 格式
        encoded_name = urllib.parse.quote(file_name, safe='')
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_name}"

    # 添加文件大小信息
    if file_size > 0:
        headers["Content-Length"] = str(file_size)
    # "Access-Control-Expose-Headers": "Content-Disposition, Content-Length, X-Filename",
    headers["Access-Control-Expose-Headers"] = "Content-Disposition, Content-Length, X-Filename"
    return headers


# 在你的路由函数中使用：
@router.get("/v1/download/file")
async def download_file(
        uri: str = Query(..., description="文件URI或路径"),
        delete_after_download: bool = Query(False),
        fs: FileStorageClient = Depends(get_fs)
):
    try:
        # validate
        if not uri.startswith("dbgpt-fs://"):
            raise HTTPException(status_code=400, detail="URI格式不正确，请使用dbgpt-fs://开头")

        # 从分布式文件系统获取文件数据和元数据
        data, file_metadata = fs.get_file(uri)
        file_name = file_metadata.file_name.split('/')[-1]

        # 支持的文件类型映射
        mimetypes.init()
        file_extension = Path(file_name).suffix.lower()
        media_type = mimetypes.types_map.get(file_extension, 'application/octet-stream')

        # 异步文件读取生成器
        async def file_generator() -> AsyncGenerator[bytes, None]:
            try:
                while True:
                    chunk = data.read(8192)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if hasattr(data, 'close'):
                    data.close()

                if delete_after_download:
                    try:
                        fs.delete_file(uri)
                        logger.info(f"file deleted: {uri}")
                    except Exception as delete_error:
                        logger.error(f"file delete error: {uri}")

        # 使用修复后的头部构建函数
        headers = build_download_headers(file_name, file_metadata.file_size)

        return StreamingResponse(
            file_generator(),
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error(f"downloading file error: {e}")
        raise HTTPException(status_code=500, detail="insight server error")