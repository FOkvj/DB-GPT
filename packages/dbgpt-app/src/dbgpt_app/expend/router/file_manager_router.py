from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from dbgpt._private.config import Config
from dbgpt.core.schema.api import Result
from dbgpt_app.expend.dao.file_process_dao import (
    FileProcessingDao,
    FileProcessingRequest,
    FileProcessingResponse,
    FileProcessingPageRequest,
    PaginationResult,
    SourceType,
    ProcessStatus
)




class BatchRequest(BaseModel):
    file_ids: List[str]



# Router 定义
router = APIRouter()
CFG = Config()
dao = FileProcessingDao()

@router.post("/file-processing", response_model=Result[FileProcessingResponse])
async def create_file_processing(
        request: FileProcessingRequest,
        
):
    """创建文件处理记录"""
    try:
        result = dao.create_file_processing(
            file_id=request.file_id,
            file_name=request.file_name,
            source_type=request.source_type.value if request.source_type else None,
            source_id=request.source_id,
            file_type=request.file_type,
            size=request.size,
            status=request.status.value if request.status else ProcessStatus.WAIT.value
        )

        if result:
            return Result.succ(result)
        else:
            return Result.failed("创建文件处理记录失败", "E500")
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/file/{file_id}", response_model=Result[FileProcessingResponse])
async def get_file_processing_by_file_id(
        file_id: str,
        
):
    """根据文件ID获取文件处理记录"""
    try:
        result = dao.get_file_processing_by_file_id(file_id)
        if result:
            return Result.succ(result)
        else:
            return Result.failed("文件处理记录不存在", "E404")
    except Exception as e:
        return Result.failed(str(e), "E500")



@router.delete("/file-processing/{record_id}", response_model=Result[bool])
async def delete_file_processing(
        record_id: int,
        
):
    """删除文件处理记录"""
    try:
        result = dao.delete_file_processing(record_id)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.delete("/file-processing/file/{file_id}", response_model=Result[bool])
async def delete_file_processing_by_file_id(
        file_id: str,
        
):
    """根据文件ID删除文件处理记录"""
    try:
        result = dao.delete_file_processing_by_file_id(file_id)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing", response_model=Result[List[FileProcessingResponse]])
async def get_file_processing_list(
        source_type: Optional[SourceType] = Query(None, description="源类型"),
        source_id: Optional[str] = Query(None, description="源ID"),
        file_type: Optional[str] = Query(None, description="文件类型"),
        status: Optional[ProcessStatus] = Query(None, description="处理状态"),
        
):
    """获取文件处理记录列表"""
    try:
        filters = {}
        if source_type:
            filters['source_type'] = source_type.value
        if source_id:
            filters['source_id'] = source_id
        if file_type:
            filters['file_type'] = file_type
        if status:
            filters['status'] = status.value

        result = dao.get_file_processing_list(**filters)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/source-type/{source_type}", response_model=Result[List[FileProcessingResponse]])
async def get_files_by_source_type(
        source_type: SourceType,
        
):
    """根据源类型获取文件列表"""
    try:
        result = dao.get_files_by_source_type(source_type.value)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/status/{status}", response_model=Result[List[FileProcessingResponse]])
async def get_files_by_status(
        status: ProcessStatus,
        
):
    """根据状态获取文件列表"""
    try:
        result = dao.get_files_by_status(status.value)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/status/processing", response_model=Result[List[FileProcessingResponse]])
async def get_processing_files(
        
):
    """获取正在处理的文件列表"""
    try:
        result = dao.get_processing_files()
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/status/failed", response_model=Result[List[FileProcessingResponse]])
async def get_failed_files(
        
):
    """获取处理失败的文件列表"""
    try:
        result = dao.get_failed_files()
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/status/waiting", response_model=Result[List[FileProcessingResponse]])
async def get_waiting_files(
        
):
    """获取等待处理的文件列表"""
    try:
        result = dao.get_waiting_files()
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.post("/file-processing/list", response_model=Result[PaginationResult[FileProcessingResponse]])
async def get_file_processing_list(
        request: FileProcessingPageRequest,
        
):
    """分页查询文件处理记录"""
    try:
        result = dao.get_file_processing_page(request)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.post("/file-processing/count", response_model=Result[int])
async def get_file_processing_count(
    request: FileProcessingRequest
):
    """获取符合条件的文件处理记录数量"""
    try:
        result = dao.get_count(request)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.post("/file-processing/batch/delete", response_model=Result[int])
async def batch_delete(
        request: BatchRequest,
        
):
    """批量删除记录"""
    try:
        result = dao.batch_delete(request.file_ids)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.post("/file-processing/reprocess", response_model=Result[int])
async def reprocess_files(
        request: BatchRequest,
        
):
    """重新处理指定文件"""
    try:
        result = dao.batch_update_status(request.file_ids, ProcessStatus.WAIT.value)
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/statistics/status", response_model=Result[dict])
async def get_status_statistics(
        
):
    """获取状态统计"""
    try:
        result = dao.get_status_statistics()
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/statistics/source-type", response_model=Result[dict])
async def get_source_type_statistics(
        
):
    """获取源类型统计"""
    try:
        result = dao.get_source_type_statistics()
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/file-processing/statistics/all", response_model=Result[dict])
async def get_all_statistics():
    """获取所有统计信息"""
    try:
        status_stats = dao.get_status_statistics()
        source_type_stats = dao.get_source_type_statistics()

        result = {
            "status_statistics": status_stats,
            "source_type_statistics": source_type_stats
        }
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.delete("/file-processing/clear", response_model=Result[bool])
async def clear_all_records(
        
):
    """清空所有记录"""
    try:
        result = dao.clear_all_records()
        return Result.succ(result)
    except Exception as e:
        return Result.failed(str(e), "E500")