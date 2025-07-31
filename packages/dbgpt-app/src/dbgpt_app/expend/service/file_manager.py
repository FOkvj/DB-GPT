# import json
# import logging
# from dataclasses import dataclass
# from datetime import datetime
# from enum import Enum
# from pathlib import Path
# from typing import List, Dict, Optional
#
# from pydantic import BaseModel
#
# from dbgpt import BaseComponent
# from dbgpt._private.config import Config
# from dbgpt.component import ComponentType, SystemApp
# from dbgpt_app.expend.dao.knowledge_mapping_dao import KnowledgeBaseMappingDao, KnowledgeBaseMappingDaoRequest
# from dbgpt_app.expend.model.knowledge_mapping import KnowledgeBaseMappingRequest, KnowledgeBaseMappingConfig
# from dbgpt_app.expend.service.speech2text import Speech2TextService
#
# # 导入现有的管道系统组件
#
# CFG = Config()
# logger = logging.getLogger(__name__)
# class FileStatus(Enum):
#     """文件状态枚举"""
#     PENDING = "pending"  # 待处理
#     PROCESSING = "processing"  # 处理中
#     COMPLETED = "completed"  # 已完成
#     FAILED = "failed"  # 处理失败
#     SKIPPED = "skipped"  # 已跳过
#
#
# @dataclass
# class FileInfo:
#     """文件信息数据类"""
#     path: str
#     name: str
#     size: int
#     created_time: str
#     modified_time: str
#     extension: str
#     status: FileStatus
#     processors: List[str]
#     last_processed: Optional[str] = None
#     error_message: Optional[str] = None
#
#
# class FileManager:
#     """文件管理器 - 负责文件操作和状态查询"""
#
#     def __init__(self, watch_paths: List[Path], event_manager: PipelineEventManager):
#         self.watch_paths = watch_paths
#         self.event_manager = event_manager
#
#     def get_file_list(self) -> List[FileInfo]:
#         """获取所有监控目录下的文件列表"""
#         files = []
#
#         for watch_path in self.watch_paths:
#             if not watch_path.exists():
#                 continue
#
#             for file_path in watch_path.rglob('*'):
#                 if not file_path.is_file():
#                     continue
#
#                 try:
#                     stat = file_path.stat()
#
#                     # 获取文件处理历史
#                     history = self.event_manager.get_file_processing_history(str(file_path))
#                     status, processors, last_processed, error_msg = self._analyze_file_status(history)
#
#                     file_info = FileInfo(
#                         path=str(file_path),
#                         name=file_path.name,
#                         size=stat.st_size,
#                         created_time=datetime.fromtimestamp(stat.st_ctime).isoformat(),
#                         modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
#                         extension=file_path.suffix.lower(),
#                         status=status,
#                         processors=processors,
#                         last_processed=last_processed,
#                         error_message=error_msg
#                     )
#
#                     files.append(file_info)
#
#                 except Exception:
#                     continue
#
#         return sorted(files, key=lambda x: x.modified_time, reverse=True)
#
#     def _analyze_file_status(self, history: List[Dict]) -> tuple:
#         """分析文件处理状态"""
#         if not history:
#             return FileStatus.PENDING, [], None, None
#
#         processors = []
#         last_processed = None
#         error_msg = None
#         has_success = False
#         has_failure = False
#
#         for event in history:
#             if event.get('processor_name'):
#                 processor_name = event['processor_name']
#                 if processor_name not in processors:
#                     processors.append(processor_name)
#
#                 result = event.get('result')
#                 if result == ProcessResult.SUCCESS.value:
#                     has_success = True
#                     last_processed = event.get('created_time')
#                 elif result == ProcessResult.FAILED.value:
#                     has_failure = True
#                     try:
#                         metadata = json.loads(event.get('metadata', '{}'))
#                         error_msg = metadata.get('error', '处理失败')
#                     except:
#                         error_msg = '处理失败'
#
#         # 确定状态
#         if has_success and not has_failure:
#             status = FileStatus.COMPLETED
#         elif has_failure:
#             status = FileStatus.FAILED
#         elif processors:
#             status = FileStatus.PROCESSING
#         else:
#             status = FileStatus.PENDING
#
#         return status, processors, last_processed, error_msg
#
#     def delete_files(self, file_paths: List[str]) -> Dict[str, bool]:
#         """批量删除文件"""
#         results = {}
#
#         for file_path in file_paths:
#             try:
#                 path = Path(file_path)
#                 if path.exists() and path.is_file():
#                     # 检查文件是否在监控目录内
#                     if any(str(path).startswith(str(watch_path)) for watch_path in self.watch_paths):
#                         path.unlink()
#                         results[file_path] = True
#                     else:
#                         results[file_path] = False  # 不在监控目录内
#                 else:
#                     results[file_path] = False  # 文件不存在
#             except Exception:
#                 results[file_path] = False
#
#         return results
#
#
# class PipelineController:
#     """管道控制器 - 负责管道系统的启动和停止"""
#
#     def __init__(self, watch_paths: List[str]):
#         self.watch_paths = watch_paths
#         self.pipeline: Optional[FilePipelineSystem] = None
#         self.is_running = False
#         self.config = {
#             'worker_count': 2,
#             'queue_size': 100
#         }
#         self.init()
#
#     def init(self):
#         from dbgpt_app.expend.service.file_monitor_v2 import AudioToTextProcessor, KnowledgeProcessor
#
#         # 创建管道系统
#         self.pipeline = FilePipelineSystem(self.watch_paths, self.config)
#         # 全局管理器实例 (在应用启动时初始化)
#         voice2text_service = CFG.SYSTEM_APP.get_component(ComponentType.SPEECH_TO_TEXT, Speech2TextService)
#
#         # 注册处理器
#         audio_processor = AudioToTextProcessor(voice2text_service, {
#             'output_dir': './output/transcripts'
#         })
#         self.pipeline.register_processor(audio_processor)
#
#         knowledge_processor = KnowledgeProcessor({
#             'output_dir': './output/knowledge'
#         })
#         self.pipeline.register_processor(knowledge_processor)
#
#     def start_pipeline(self) -> bool:
#         """启动管道系统"""
#         if self.is_running:
#             return True
#
#         try:
#             # 启动系统
#             self.pipeline.start()
#             self.is_running = True
#             return True
#
#         except Exception as e:
#             logger.error(f"启动管道系统失败: {e}")
#             return False
#
#     def stop_pipeline(self) -> bool:
#         """停止管道系统"""
#         if not self.is_running or not self.pipeline:
#             return True
#
#         try:
#             self.pipeline.stop()
#             self.is_running = False
#             return True
#         except Exception as e:
#             logger.error(f"停止管道系统失败: {e}")
#             return False
#
#     def get_status(self) -> Dict:
#         """获取管道状态"""
#         if not self.is_running or not self.pipeline:
#             return {
#                 'running': False,
#                 'queue_size': 0,
#                 'worker_count': 0,
#                 'processor_statistics': {}
#             }
#
#         return self.pipeline.get_system_status()
#
#
# # Pydantic 请求模型
# class DeleteFilesRequest(BaseModel):
#     file_paths: List[str]
#
#
# class PipelineControlRequest(BaseModel):
#     action: str  # "start" or "stop"
#
#
# class PipelineWebManager(BaseComponent):
#     """管道Web管理器 - 系统单例管理类"""
#     name = ComponentType.PIPELINE_MANAGER
#
#     def __init__(self, watch_paths: List[str], **kwargs):
#         super().__init__(**kwargs)
#         self.watch_paths = [Path(p) for p in watch_paths]
#         self.event_manager = PipelineEventManager()
#         self.file_manager = FileManager(self.watch_paths, self.event_manager)
#         self.pipeline_controller = PipelineController(watch_paths)
#         self.knowledge_mapping_dao = KnowledgeBaseMappingDao()
#
#         # 确保监控目录存在
#         for path in self.watch_paths:
#             path.mkdir(parents=True, exist_ok=True)
#
#     def init_app(self, system_app: SystemApp):
#         pass
#
#     def get_knowledge_mappings(self) -> List[Dict]:
#         """获取知识库映射配置"""
#         return self.knowledge_mapping_dao.get_all_mappings()
#
#     def save_knowledge_mappings(self, mappings: List[KnowledgeBaseMappingConfig]):
#         """保存知识库映射配置"""
#         dao_requests = [KnowledgeBaseMappingDaoRequest(**mapping.dict()) for mapping in mappings]
#         self.knowledge_mapping_dao.save_mappings(dao_requests)
