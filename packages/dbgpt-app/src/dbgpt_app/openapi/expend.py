import json
import logging
import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, File, Query, UploadFile
from fastapi import Form
from sqlalchemy import inspect

from dbgpt_app.expend.excel2db import ExtendedMySQLConnector, ExcelToMysql
from dbgpt_app.openapi.api_view_model import (
    Result,
)

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

                # # 提取表结构信息用于前端展示（只提取第一个表的信息作为table_data）
                # if table_data == [] and file_result["success"]:
                #     # 获取第一个工作表的名称
                #     first_sheet_name = next(iter(file_result["sheets"]))
                #     sheet_result = file_result["sheets"][first_sheet_name]
                #
                #     # 如果成功，则获取表结构
                #     if sheet_result["success"]:
                #         table_name = importer._get_table_name(first_sheet_name)
                #         inspector = inspect(connector._engine)
                #         columns = inspector.get_columns(table_name)
                #
                #         # 格式化列信息以供前端显示（用于旧的tableData结构）
                #         for i, col in enumerate(columns):
                #             table_data.append({
                #                 "key": str(i + 1),
                #                 "column": col["name"],
                #                 "type": str(col["type"]),
                #                 "mapped": col.get("mapped", col["name"])
                #             })

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
