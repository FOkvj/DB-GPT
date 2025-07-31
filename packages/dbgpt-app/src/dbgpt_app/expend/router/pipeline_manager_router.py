from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dbgpt._private.config import Config
from dbgpt.core.schema.api import Result
from dbgpt_app.expend.dao.file_process_dao import SourceType, FileProcessingResponse
from dbgpt_app.expend.dependencies import get_pipeline_manager
from dbgpt_app.expend.model.knowledge_mapping import KnowledgeBaseMappingRequest
from dbgpt_app.expend.service.pipeline_manager import PipelineManager

CFG = Config()


# 请求模型



class ProcessorControlRequest(BaseModel):
    action: str  # "start", "stop", "restart"
    processor_name: Optional[str] = None


class ReprocessFileRequest(BaseModel):
    file_ids: List[str]




# Router 定义
router = APIRouter()


@router.get("/knowledge-mappings")
async def get_knowledge_mappings(manager: PipelineManager = Depends(get_pipeline_manager)):
    """获取知识库映射配置"""
    try:
        mappings = manager.get_knowledge_mappings()
        return Result.succ(mappings)
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.post("/knowledge-mappings")
async def save_knowledge_mappings(
    request: KnowledgeBaseMappingRequest,
    manager: PipelineManager = Depends(get_pipeline_manager)
):
    """保存知识库映射配置"""
    try:
        manager.save_knowledge_mappings(request.mappings)
        return Result.succ({"message": "知识库映射配置保存成功"})
    except Exception as e:
        return Result.failed(str(e), "E500")

# 删除mapping
@router.post("/knowledge-mappings/delete")
async def delete_knowledge_mappings(
    request: KnowledgeBaseMappingRequest,
    manager: PipelineManager = Depends(get_pipeline_manager)
):
    """删除知识库映射配置"""
    try:
        manager.delete_knowledge_mappings(request.mappings)
        return Result.succ({"message": "知识库映射配置删除成功"})
    except Exception as e:
        return Result.failed(str(e), "E500")



@router.post("/pipeline/reprocess")
async def reprocess_files(
        request: ReprocessFileRequest,
        manager: PipelineManager = Depends(get_pipeline_manager)
):
    """重新处理指定文件"""
    try:
        return Result.succ(manager.reprocess_files(request.file_ids))
    except Exception as e:
        return Result.failed(str(e), "E500")


@router.get("/processors/status")
async def get_processors_status(manager: PipelineManager = Depends(get_pipeline_manager)):
    """获取处理器状态"""
    try:
        processors_info = {}

        for name, processor in manager.processor_manager.processors.items():
            processors_info[name] = {
                "name": processor.name,
                "topic": processor.topic,
                "enabled": processor.enabled,
                "consuming": processor.consumer is not None and processor.consumer.is_consuming(),
            }

        return Result.succ({
            "processors": processors_info,
            "total_processors": len(processors_info)
        })

    except Exception as e:
        return Result.failed(str(e), "E500")


@router.post("/processors/control")
async def control_processors(
        request: ProcessorControlRequest,
        manager: PipelineManager = Depends(get_pipeline_manager)
):
    """控制处理器启动/停止/重启"""
    try:
        results = {}

        if request.processor_name:
            # 操作指定处理器
            processor = manager.processor_manager.get_processor(request.processor_name)
            if not processor:
                return Result.failed(f"处理器 {request.processor_name} 不存在", "E404")

            try:
                if request.action == "start":
                    processor.start_consuming()
                    results[request.processor_name] = "started"
                elif request.action == "stop":
                    processor.stop_consuming()
                    results[request.processor_name] = "stopped"
                elif request.action == "restart":
                    processor.stop_consuming()
                    processor.start_consuming()
                    results[request.processor_name] = "restarted"
                else:
                    return Result.failed(f"无效的操作: {request.action}", "E400")

            except Exception as e:
                results[request.processor_name] = f"failed: {str(e)}"
        else:
            # 操作所有处理器
            for name, processor in manager.processor_manager.processors.items():
                try:
                    if request.action == "start":
                        processor.start_consuming()
                        results[name] = "started"
                    elif request.action == "stop":
                        processor.stop_consuming()
                        results[name] = "stopped"
                    elif request.action == "restart":
                        processor.stop_consuming()
                        processor.start_consuming()
                        results[name] = "restarted"
                except Exception as e:
                    results[name] = f"failed: {str(e)}"

        return Result.succ({
            "action": request.action,
            "results": results
        })

    except Exception as e:
        return Result.failed(str(e), "E500")
