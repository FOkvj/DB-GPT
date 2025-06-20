#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件管道管理模块
提供文件管理和管道控制功能
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from dbgpt.core.schema.api import Result
from dbgpt_app.expend.dependencies import get_pipeline_manager
from dbgpt_app.expend.service.file_manager import PipelineWebManager, DeleteFilesRequest, PipelineControlRequest

# Router 定义
router = APIRouter()


@router.get("/files")
async def get_files(manager: PipelineWebManager = Depends(get_pipeline_manager)):
    """获取文件列表"""
    try:
        files = manager.file_manager.get_file_list()
        return Result.succ([asdict(file) for file in files])
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.delete("/files")
async def delete_files(
    request: DeleteFilesRequest,
    manager: PipelineWebManager = Depends(get_pipeline_manager)
):
    """批量删除文件"""
    try:
        results = manager.file_manager.delete_files(request.file_paths)
        success_count = sum(1 for r in results.values() if r)

        return Result.succ({
            "results": results,
            "success_count": success_count,
            "total_count": len(request.file_paths)
        })
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.get("/pipeline/status")
async def get_pipeline_status(manager: PipelineWebManager = Depends(get_pipeline_manager)):
    """获取管道状态"""
    try:
        status = manager.pipeline_controller.get_status()
        return Result.succ(status)
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.post("/pipeline/control")
async def control_pipeline(
    request: PipelineControlRequest,
    manager: PipelineWebManager = Depends(get_pipeline_manager)
):
    """控制管道启动/停止"""
    try:
        if request.action == "start":
            success = manager.pipeline_controller.start_pipeline()
        elif request.action == "stop":
            success = manager.pipeline_controller.stop_pipeline()
        else:
            return Result.failed("Invalid action", "E400")

        if success:
            return Result.succ({
                "action": request.action,
                "status": "completed"
            })
        else:
            return Result.failed(f"Failed to {request.action} pipeline", "E500")
    except Exception as e:
        return Result.failed(str(e), "E500")

