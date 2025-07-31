#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PipelineManager作为Service层
"""
from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass

from dbgpt.component import ComponentType, BaseComponent, SystemApp
from dbgpt._private.config import Config
from dbgpt_app.expend.dao.file_process_dao import FileProcessingDao, SourceType, ProcessStatus, FileProcessingResponse
from dbgpt_app.expend.dao.knowledge_mapping_dao import KnowledgeBaseMappingDaoRequest, KnowledgeBaseMappingDao
from dbgpt_app.expend.model.knowledge_mapping import KnowledgeBaseMappingConfig
from dbgpt_app.expend.service.processor_manager import MessageQueueProcessorManager
from dbgpt_app.expend.service.queue.mq import RabbitMQManager
from dbgpt_app.expend.utils.file_type_utils import get_topic_by_file_type

CFG = Config()




class PipelineManager(BaseComponent):
    """管道管理器 - Service层"""
    name = ComponentType.PIPELINE_MANAGER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # DAO层
        self._file_process_dao = FileProcessingDao()
        self.knowledge_mapping_dao = KnowledgeBaseMappingDao()

        self.mq_manager: RabbitMQManager = CFG.SYSTEM_APP.get_component(
            ComponentType.MESSAGE_QUEUE_MANAGER,
            RabbitMQManager
        )

        self.processor_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.QUEUE_PROCESSOR_MANAGER,
            MessageQueueProcessorManager
        )

    def init_app(self, system_app: SystemApp):
        pass

    def get_knowledge_mappings(self) -> List[Dict]:
        """获取知识库映射配置"""
        return self.knowledge_mapping_dao.get_all_mappings()

    def save_knowledge_mappings(self, mappings: List[KnowledgeBaseMappingConfig]):
        """保存知识库映射配置"""
        dao_requests = [KnowledgeBaseMappingDaoRequest(**mapping.dict()) for mapping in mappings]
        self.knowledge_mapping_dao.save_mappings(dao_requests)

    def delete_knowledge_mappings(
        self,
        mappings: List[KnowledgeBaseMappingConfig]
    ):
        for mapping in mappings:
            self.knowledge_mapping_dao.delete({"id": mapping.id})

    def get_processors_status(self) -> Dict[str, any]:
        """获取处理器状态"""
        try:
            processors_info = {}

            for name, processor in self.processor_manager.processors.items():
                processors_info[name] = {
                    "name": processor.name,
                    "topic": processor.topic,
                    "enabled": processor.enabled,
                    "consuming": processor.consumer is not None and processor.consumer.is_consuming(),
                    "statistics": processor.get_statistics()
                }

            return {
                "processors": processors_info,
                "total_processors": len(processors_info)
            }
        except Exception as e:
            raise Exception(f"获取处理器状态失败: {e}")

    def control_processors(self, action: str, processor_name: Optional[str] = None) -> Dict[str, any]:
        """控制处理器启动/停止/重启"""
        try:
            results = {}

            if processor_name:
                processor = self.processor_manager.get_processor(processor_name)
                if not processor:
                    raise Exception(f"处理器 {processor_name} 不存在")

                try:
                    if action == "start":
                        processor.start_consuming()
                        results[processor_name] = "started"
                    elif action == "stop":
                        processor.stop_consuming()
                        results[processor_name] = "stopped"
                    elif action == "restart":
                        processor.stop_consuming()
                        processor.start_consuming()
                        results[processor_name] = "restarted"
                    else:
                        raise Exception(f"无效的操作: {action}")
                except Exception as e:
                    results[processor_name] = f"failed: {str(e)}"
            else:
                for name, processor in self.processor_manager.processors.items():
                    try:
                        if action == "start":
                            processor.start_consuming()
                            results[name] = "started"
                        elif action == "stop":
                            processor.stop_consuming()
                            results[name] = "stopped"
                        elif action == "restart":
                            processor.stop_consuming()
                            processor.start_consuming()
                            results[name] = "restarted"
                    except Exception as e:
                        results[name] = f"failed: {str(e)}"

            return {
                "action": action,
                "results": results
            }
        except Exception as e:
            raise Exception(f"控制处理器失败: {e}")

    def reprocess_files(self, file_ids: List[str]) -> Dict[str, any]:
        """重新处理指定文件"""
        try:
            reprocessed_files = []
            failed_files = []

            for file_id in file_ids:
                try:
                    file_info = self._file_process_dao.get_file_processing_by_file_id(file_id)
                    if not file_info:
                        failed_files.append({
                            "file_id": file_id,
                            "error": "文件信息未找到"
                        })
                        continue
                    target_topic = get_topic_by_file_type(file_info.file_type)
                    self.mq_manager.publish_point_to_point(target_topic, file_info)
                    reprocessed_files.append(file_id)

                except Exception as e:
                    failed_files.append({
                        "file_id": file_id,
                        "error": str(e)
                    })

            return {
                "reprocessed_files": reprocessed_files,
                "failed_files": failed_files,
                "total_count": len(file_ids),
                "success_count": len(reprocessed_files)
            }
        except Exception as e:
            raise Exception(f"重新处理文件失败: {e}")

    def health_check(self) -> Dict[str, any]:
        """系统健康检查"""
        try:
            health_info = {
                "timestamp": "now",
                "components": {},
                "overall_status": "healthy"
            }

            # 检查消息队列
            try:
                producer = self.mq_manager.get_producer()
                health_info["components"]["message_queue"] = {
                    "status": "healthy" if producer.is_connected() else "unhealthy",
                    "connected": producer.is_connected()
                }
            except Exception as e:
                health_info["components"]["message_queue"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }

            # 检查处理器
            try:
                active_processors = 0
                total_processors = len(self.processor_manager.processors)

                for processor in self.processor_manager.processors.values():
                    if processor.consumer and processor.consumer.is_consuming():
                        active_processors += 1

                health_info["components"]["processors"] = {
                    "status": "healthy" if active_processors > 0 else "warning",
                    "active_processors": active_processors,
                    "total_processors": total_processors
                }
            except Exception as e:
                health_info["components"]["processors"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }

            # 检查数据库
            try:
                self._file_process_dao.get_status_statistics()
                health_info["components"]["database"] = {
                    "status": "healthy",
                    "accessible": True
                }
            except Exception as e:
                health_info["components"]["database"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }

            # 判断整体状态
            unhealthy_components = [
                name for name, info in health_info["components"].items()
                if info["status"] == "unhealthy"
            ]

            if unhealthy_components:
                health_info["overall_status"] = "unhealthy"
                health_info["unhealthy_components"] = unhealthy_components
            elif any(info["status"] == "warning" for info in health_info["components"].values()):
                health_info["overall_status"] = "warning"

            return health_info
        except Exception as e:
            raise Exception(f"健康检查失败: {e}")


