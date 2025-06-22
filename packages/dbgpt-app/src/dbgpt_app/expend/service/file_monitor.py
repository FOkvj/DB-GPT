# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# 模块化文件处理管道系统
# 支持插件化的处理器架构，实现解耦和可扩展性
# 改进：启动时扫描现有文件并检查处理状态
# """
# import asyncio
# import os
# import time
# import threading
# import queue
# import logging
# import sqlite3
# import hashlib
# import json
# from concurrent.futures import ThreadPoolExecutor
# from pathlib import Path
# from typing import List, Dict, Optional, Callable, Any, Tuple
# from datetime import datetime
# from enum import Enum
# from abc import ABC, abstractmethod
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# from voice2text.tran.funasr_transcriber import FunASRTranscriber
#
# from dbgpt.core.interface.file import FileStorageClient
# from dbgpt.rag.knowledge.base import KnowledgeType
# from dbgpt_app.expend.service.speech2text import Speech2TextService
# from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest, KnowledgeDocumentRequest
# from dbgpt_app.knowledge.service import KnowledgeService, CFG
# from dbgpt_ext.rag import ChunkParameters
# from dbgpt_serve.core import blocking_func_to_async
# from dbgpt_serve.rag.api.schemas import KnowledgeSyncRequest
# from dbgpt_serve.rag.service.service import Service
#
# # 配置日志
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
#
#
# class ProcessResult(Enum):
#     """处理结果状态"""
#     SUCCESS = "success"
#     FAILED = "failed"
#     SKIPPED = "skipped"
#     PARTIAL = "partial"
#
#
# class FileEvent:
#     """文件事件对象"""
#
#     def __init__(self, file_path: str, event_type: str = "created",
#                  metadata: Dict = None, source_processor: str = None):
#         self.file_path = Path(file_path).absolute()
#         self.event_type = event_type
#         self.timestamp = datetime.now()
#         self.metadata = metadata or {}
#         self.source_processor = source_processor  # 产生此文件的处理器
#         self.file_hash = self._calculate_hash()
#
#     def _calculate_hash(self) -> str:
#         """计算文件哈希"""
#         try:
#             if self.file_path.exists():
#                 with open(self.file_path, 'rb') as f:
#                     return hashlib.md5(f.read()).hexdigest()
#         except:
#             pass
#         return ""
#
#     def to_dict(self) -> Dict:
#         """转换为字典"""
#         return {
#             'file_path': str(self.file_path),
#             'event_type': self.event_type,
#             'timestamp': self.timestamp.isoformat(),
#             'metadata': self.metadata,
#             'source_processor': self.source_processor,
#             'file_hash': self.file_hash
#         }
#
#
# class ProcessorInterface(ABC):
#     """处理器接口基类"""
#
#     def __init__(self, name: str, config: Dict = None):
#         self.name = name
#         self.config = config or {}
#         self.logger = logging.getLogger(f"processor.{name}")
#         self.enabled = True
#         self.statistics = {
#             'processed': 0,
#             'success': 0,
#             'failed': 0,
#             'skipped': 0
#         }
#
#     @abstractmethod
#     def can_process(self, file_event: FileEvent) -> bool:
#         """判断是否可以处理此文件"""
#         pass
#
#     @abstractmethod
#     async def process(self, file_event: FileEvent) -> Tuple[ProcessResult, Optional[List[str]], Dict]:
#         """
#         处理文件
#         返回: (结果状态, 生成的文件列表, 元数据)
#         """
#         pass
#
#     @abstractmethod
#     def get_supported_extensions(self) -> List[str]:
#         """获取支持的文件扩展名"""
#         pass
#
#     def get_output_directory(self) -> Optional[Path]:
#         """获取输出目录"""
#         return self.config.get('output_dir')
#
#     def setup(self):
#         """初始化设置"""
#         output_dir = self.get_output_directory()
#         if output_dir:
#             Path(output_dir).mkdir(parents=True, exist_ok=True)
#
#     def cleanup(self):
#         """清理资源"""
#         pass
#
#     def get_statistics(self) -> Dict:
#         """获取处理统计"""
#         return self.statistics.copy()
#
#     def update_statistics(self, result: ProcessResult):
#         """更新统计信息"""
#         self.statistics['processed'] += 1
#         if result == ProcessResult.SUCCESS:
#             self.statistics['success'] += 1
#         elif result == ProcessResult.FAILED:
#             self.statistics['failed'] += 1
#         elif result == ProcessResult.SKIPPED:
#             self.statistics['skipped'] += 1
#
#     def check_if_already_processed(self, file_event: FileEvent, event_manager) -> bool:
#         """检查文件是否已被此处理器成功处理过"""
#         history = event_manager.get_file_processing_history(str(file_event.file_path))
#
#         for event in history:
#             if (event['processor_name'] == self.name and
#                     event['result'] == ProcessResult.SUCCESS.value and
#                     event.get('file_hash') == file_event.file_hash):
#                 return True
#         return False
#
#     def get_expected_output_files(self, file_event: FileEvent) -> List[str]:
#         """获取此文件预期的输出文件列表（用于检查是否已处理）"""
#         # 默认实现，子类可以重写
#         return []
#
#
# class AudioToTextProcessor(ProcessorInterface):
#     """语音转文字处理器"""
#
#     def __init__(self, tanscriber: Speech2TextService, config: Dict = None):
#         super().__init__("audio_to_text", config)
#         self.supported_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.aac']
#         self.transcriber = tanscriber
#
#
#     def can_process(self, file_event: FileEvent) -> bool:
#         """检查是否可以处理音频文件"""
#         if not self.enabled:
#             return False
#
#         # 检查文件扩展名
#         if file_event.file_path.suffix.lower() not in self.supported_extensions:
#             return False
#
#         # 避免处理由其他处理器生成的文件
#         if file_event.source_processor:
#             return False
#
#         return True
#
#     async def process(self, file_event: FileEvent) -> Tuple[ProcessResult, Optional[List[str]], Dict]:
#         """执行语音转文字"""
#         try:
#             self.logger.info(f"开始语音转文字: {file_event.file_path.name}")
#
#             # 检查文件是否存在且不为空
#             if not file_event.file_path.exists() or file_event.file_path.stat().st_size == 0:
#                 return ProcessResult.FAILED, None, {"error": "文件不存在或为空"}
#
#             # 生成输出文件路径
#             output_dir = Path(self.get_output_directory() or "./output/transcripts")
#             output_dir.mkdir(parents=True, exist_ok=True)
#
#             output_file = output_dir / f"{file_event.file_path.stem}_transcript.txt"
#
#             # TODO: 集成实际的语音转文字引擎
#             # 这里使用占位实现
#
#             # 尝试从文件名解析位置和时间信息
#             # location, date, record_time = parse_filename(file.filename)
#
#             # 使用FunASR转写服务处理文件
#             process_start_time = time.time()
#
#             transcription_result = self.transcriber.transcribe_file(audio_file_path=file_event.file_path.as_posix(), threshold=0.5)
#
#             # 提取结果
#             transcript_text = transcription_result["transcript"]
#             duration = transcription_result["audio_duration"]
#             # transcript_text = "这是测试假数据"
#             output_file = transcription_result.get("output_file", "")
#
#             # 写入转换结果
#             with open(output_file, 'w', encoding='utf-8') as f:
#                 f.write(transcript_text)
#
#             # 准备元数据
#             metadata = {
#                 'original_file': str(file_event.file_path),
#                 'processor': self.name,
#                 'processing_time': datetime.now().isoformat(),
#                 'file_size': file_event.file_path.stat().st_size,
#                 'transcript_length': len(transcript_text),
#                 'language': self.config.get('language', 'auto'),
#                 'model': self.config.get('model', 'default'),
#                 'file_hash': file_event.file_hash
#             }
#
#             self.logger.info(f"语音转文字完成: {output_file.name}")
#             return ProcessResult.SUCCESS, [str(output_file)], metadata
#
#         except Exception as e:
#             self.logger.error(f"语音转文字失败: {e}")
#             return ProcessResult.FAILED, None, {"error": str(e)}
#
#     def get_supported_extensions(self) -> List[str]:
#         return self.supported_extensions
#
#     def get_expected_output_files(self, file_event: FileEvent) -> List[str]:
#         """获取预期的输出文件"""
#         output_dir = Path(self.get_output_directory() or "./output/transcripts")
#         output_file = output_dir / f"{file_event.file_path.stem}_transcript.txt"
#         return [str(output_file)]
#
#
# class KnowledgeProcessor(ProcessorInterface):
#     """知识库加工处理器"""
#
#     def __init__(self, config: Dict = None):
#         super().__init__("knowledge_processor", config)
#         self.supported_extensions = ['.txt', '.md']
#         self.knowledge_space_service = KnowledgeService()
#
#     def can_process(self, file_event: FileEvent) -> bool:
#         """检查是否可以处理文本文件"""
#         if not self.enabled:
#             return False
#
#         # 只处理文本文件
#         if file_event.file_path.suffix.lower() not in self.supported_extensions:
#             return False
#
#         # 优先处理来自语音转文字的结果
#         if (file_event.source_processor == "audio_to_text" or
#                 "_transcript" in file_event.file_path.name):
#             return True
#
#         # 也可以处理其他文本文件
#         return file_event.source_processor is None
#
#     def _create_space(self, space_name: str):
#         logger.info(f"创建知识库: {space_name}")
#         request: KnowledgeSpaceRequest = KnowledgeSpaceRequest(
#             name=space_name,
#             desc=f"自动生成的知识库: {space_name}",
#             vector_type="VectorStore",
#             domain_type="Normal",
#         )
#         self.knowledge_space_service.create_knowledge_space(request)
#
#     def _upload_file(self, file_event: FileEvent):
#         logger.info(f"上传文件: {file_event.file_path.name}")
#         # 读取文件对象
#         path = file_event.file_path
#         with open(path, 'rb') as doc_file:
#             doc_file
#             bucket = "dbgpt_knowledge_file"
#             fs = FileStorageClient.get_instance(
#                 CFG.SYSTEM_APP, default_component=None
#             )
#             space_name = file_event.file_path.stem
#             file_name = file_event.file_path.name
#             doc_type = KnowledgeType.DOCUMENT.name
#             custom_metadata = {
#                 "space_name": space_name,
#                 "doc_name": file_name,
#                 "doc_type": doc_type,
#             }
#             file_uri = fs.save_file(bucket, file_name, doc_file, custom_metadata=custom_metadata)
#
#         request = KnowledgeDocumentRequest()
#         request.doc_name = space_name
#         request.doc_type = doc_type
#         request.content = file_uri
#         result = self.knowledge_space_service.create_knowledge_document(space=space_name, request=request)
#         return result
#
#     async def _sync_doc(self, space_name: str, doc_id: int):
#         logger.info(f"开始同步文档: {space_name}, {doc_id}")
#         service = Service.get_instance(CFG.SYSTEM_APP)
#         logger.info(f"Received params: {space_name}")
#         try:
#             space = service.get({"name": space_name})
#             if space is None:
#                 raise ValueError(f"knowledge_space {space_name} can not be found")
#             if doc_id is None:
#                 logger.error("doc_ids is None")
#             sync_request = KnowledgeSyncRequest(
#                 doc_id=doc_id,
#                 space_id=str(space.id),
#                 chunk_parameters=ChunkParameters(
#                     chunk_strategy="Automatic",
#                     chunk_size=512,
#                     chunk_overlap=50,
#                 )
#             )
#             doc_ids = await service.sync_document(requests=[sync_request])
#             return doc_ids
#         except Exception as e:
#             logger.error(f"Failed to sync document: {e}")
#
#
#     async def process(self, file_event: FileEvent) -> Tuple[ProcessResult, Optional[List[str]], Dict]:
#         """执行知识加工"""
#         try:
#             space_name = file_event.file_path.stem
#             self.logger.info(f"开始知识加工: {space_name}")
#             self._create_space(space_name)
#             doc_id = self._upload_file(file_event)
#             logger.info(f"文档上传成功， doc_id: {doc_id}")
#             # 获取或创建事件循环
#             try:
#                 loop = asyncio.get_event_loop()
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 asyncio.set_event_loop(loop)
#
#             doc_ids = await self._sync_doc(space_name=space_name, doc_id=doc_id)
#
#             return ProcessResult.SUCCESS, [str(doc_id) for doc_id in doc_ids], {}
#         except Exception as e:
#             self.logger.error(f"知识加工失败: {e}")
#             return ProcessResult.FAILED, None, {"error": str(e)}
#
#     def get_supported_extensions(self) -> List[str]:
#         return self.supported_extensions
#
#
# class ProcessorRegistry:
#     """处理器注册中心"""
#
#     def __init__(self):
#         self.processors: Dict[str, ProcessorInterface] = {}
#         self.logger = logging.getLogger("processor_registry")
#
#     def register(self, processor: ProcessorInterface):
#         """注册处理器"""
#         self.processors[processor.name] = processor
#         processor.setup()
#         self.logger.info(f"已注册处理器: {processor.name}")
#
#     def unregister(self, name: str):
#         """注销处理器"""
#         if name in self.processors:
#             self.processors[name].cleanup()
#             del self.processors[name]
#             self.logger.info(f"已注销处理器: {name}")
#
#     def get_applicable_processors(self, file_event: FileEvent) -> List[ProcessorInterface]:
#         """获取可处理指定文件的处理器"""
#         applicable = []
#         for processor in self.processors.values():
#             if processor.can_process(file_event):
#                 applicable.append(processor)
#         return applicable
#
#     def get_all_processors(self) -> Dict[str, ProcessorInterface]:
#         """获取所有处理器"""
#         return self.processors.copy()
#
#     def get_statistics(self) -> Dict:
#         """获取所有处理器的统计信息"""
#         stats = {}
#         for name, processor in self.processors.items():
#             stats[name] = processor.get_statistics()
#         return stats
#
#
# class PipelineEventManager:
#     """管道事件管理器"""
#
#     def __init__(self, db_path: str = "./pipeline_events.db"):
#         self.db_path = db_path
#         self.lock = threading.RLock()
#         self.init_database()
#
#     def init_database(self):
#         """初始化数据库"""
#         with sqlite3.connect(self.db_path) as conn:
#             conn.execute("""
#                 CREATE TABLE IF NOT EXISTS pipeline_events (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     file_path TEXT NOT NULL,
#                     event_type TEXT NOT NULL,
#                     processor_name TEXT,
#                     result TEXT,
#                     metadata TEXT,
#                     created_time TEXT NOT NULL,
#                     output_files TEXT,
#                     file_hash TEXT
#                 )
#             """)
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON pipeline_events(file_path)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_processor ON pipeline_events(processor_name)")
#             conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON pipeline_events(file_hash)")
#
#     def log_event(self, file_event: FileEvent, processor_name: str = None,
#                   result: ProcessResult = None, output_files: List[str] = None,
#                   metadata: Dict = None):
#         """记录管道事件"""
#         try:
#             with self.lock:
#                 with sqlite3.connect(self.db_path) as conn:
#                     conn.execute("""
#                         INSERT INTO pipeline_events
#                         (file_path, event_type, processor_name, result, metadata, created_time, output_files, file_hash)
#                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#                     """, (
#                         str(file_event.file_path),
#                         file_event.event_type,
#                         processor_name,
#                         result.value if result else None,
#                         json.dumps(metadata or {}),
#                         file_event.timestamp.isoformat(),
#                         json.dumps(output_files or []),
#                         file_event.file_hash
#                     ))
#         except Exception as e:
#             logger.error(f"记录事件失败: {e}")
#
#     def get_file_processing_history(self, file_path: str) -> List[Dict]:
#         """获取文件的处理历史"""
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 cursor = conn.execute("""
#                     SELECT * FROM pipeline_events
#                     WHERE file_path = ?
#                     ORDER BY created_time
#                 """, (str(Path(file_path).absolute()),))
#
#                 columns = [desc[0] for desc in cursor.description]
#                 return [dict(zip(columns, row)) for row in cursor.fetchall()]
#         except Exception as e:
#             logger.error(f"获取处理历史失败: {e}")
#             return []
#
#     def is_file_processed_successfully(self, file_path: str, processor_name: str, file_hash: str) -> bool:
#         """检查文件是否已被特定处理器成功处理过"""
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 cursor = conn.execute("""
#                     SELECT COUNT(*) FROM pipeline_events
#                     WHERE file_path = ? AND processor_name = ? AND result = ? AND file_hash = ?
#                 """, (str(Path(file_path).absolute()), processor_name, ProcessResult.SUCCESS.value, file_hash))
#
#                 count = cursor.fetchone()[0]
#                 return count > 0
#         except Exception as e:
#             logger.error(f"检查处理状态失败: {e}")
#             return False
#
#     def get_unprocessed_files(self, watch_paths: List[Path], processors: Dict[str, ProcessorInterface]) -> List[
#         FileEvent]:
#         """获取未处理的文件列表"""
#         unprocessed_files = []
#
#         for watch_path in watch_paths:
#             if not watch_path.exists():
#                 continue
#
#             # 递归扫描目录中的所有文件
#             for file_path in watch_path.rglob('*'):
#                 if not file_path.is_file():
#                     continue
#
#                 try:
#                     file_event = FileEvent(str(file_path), "startup_scan")
#
#                     # 检查是否有处理器可以处理此文件
#                     applicable_processors = []
#                     for processor in processors.values():
#                         if processor.can_process(file_event):
#                             # 检查是否已被成功处理过
#                             if not self.is_file_processed_successfully(
#                                     str(file_path), processor.name, file_event.file_hash):
#                                 applicable_processors.append(processor)
#
#                     # 如果有未处理的处理器，则加入队列
#                     if applicable_processors:
#                         unprocessed_files.append(file_event)
#                         logger.debug(f"发现未处理文件: {file_path.name} "
#                                      f"(待处理器: {[p.name for p in applicable_processors]})")
#
#                 except Exception as e:
#                     logger.error(f"检查文件 {file_path} 时出错: {e}")
#
#         return unprocessed_files
#
#
# class FilePipelineSystem:
#     """文件处理管道系统"""
#
#     def __init__(self, watch_paths: List[str], config: Dict = None):
#         self.watch_paths = [Path(p) for p in watch_paths]
#         self.config = config or {}
#         self.processor_registry = ProcessorRegistry()
#         self.event_manager = PipelineEventManager()
#         self.task_queue = queue.Queue(maxsize=self.config.get('queue_size', 1000))
#         self.workers = []
#         self.observer = None
#         self.running = False
#
#         # 确保监控目录存在
#         for path in self.watch_paths:
#             path.mkdir(parents=True, exist_ok=True)
#
#     def register_processor(self, processor: ProcessorInterface):
#         """注册处理器"""
#         self.processor_registry.register(processor)
#
#     def start(self):
#         """启动管道系统"""
#         logger.info("启动文件处理管道系统...")
#
#         # 启动工作线程
#         self._start_workers()
#
#         # 扫描现有文件并加入队列
#         self._scan_existing_files()
#
#         # 启动文件监控
#         self._start_file_monitoring()
#
#         self.running = True
#         logger.info(f"系统已启动，监控路径: {[str(p) for p in self.watch_paths]}")
#
#         # 显示已注册的处理器
#         processors = self.processor_registry.get_all_processors()
#         logger.info(f"已注册处理器: {list(processors.keys())}")
#
#     def stop(self):
#         """停止管道系统"""
#         logger.info("正在停止管道系统...")
#
#         self.running = False
#
#         # 停止文件监控
#         if self.observer:
#             self.observer.stop()
#             self.observer.join()
#
#         # 等待队列处理完成
#         self.task_queue.join()
#
#         # 停止工作线程
#         for worker in self.workers:
#             worker.stop()
#
#         # 清理处理器资源
#         for processor in self.processor_registry.get_all_processors().values():
#             processor.cleanup()
#
#         logger.info("管道系统已停止")
#
#     def _scan_existing_files(self):
#         """扫描现有文件并将未处理的文件加入队列"""
#         logger.info("正在扫描现有文件...")
#
#         processors = self.processor_registry.get_all_processors()
#         unprocessed_files = self.event_manager.get_unprocessed_files(self.watch_paths, processors)
#
#         if unprocessed_files:
#             logger.info(f"发现 {len(unprocessed_files)} 个未处理的文件，正在加入处理队列...")
#
#             for file_event in unprocessed_files:
#                 try:
#                     self.task_queue.put(file_event, timeout=1)
#                 except queue.Full:
#                     logger.warning(f"队列已满，跳过文件: {file_event.file_path.name}")
#                     break
#
#             logger.info(f"已将 {len(unprocessed_files)} 个文件加入处理队列")
#         else:
#             logger.info("没有发现需要处理的现有文件")
#
#     def _start_workers(self):
#         """启动工作线程"""
#         worker_count = self.config.get('worker_count', 3)
#
#         for i in range(worker_count):
#             worker = PipelineWorker(
#                 self.task_queue,
#                 self.processor_registry,
#                 self.event_manager,
#                 self._on_file_processed
#             )
#             thread = threading.Thread(target=worker.run, name=f"PipelineWorker-{i + 1}")
#             thread.daemon = True
#             thread.start()
#             self.workers.append(worker)
#
#         logger.info(f"已启动 {worker_count} 个工作线程")
#
#     def _start_file_monitoring(self):
#         """启动文件监控"""
#         event_handler = PipelineFileHandler(self.task_queue, self.processor_registry)
#         self.observer = Observer()
#
#         for watch_path in self.watch_paths:
#             self.observer.schedule(event_handler, str(watch_path), recursive=True)
#
#         self.observer.start()
#         logger.info("文件监控已启动")
#
#     def _on_file_processed(self, file_event: FileEvent, processor: ProcessorInterface,
#                            result: ProcessResult, output_files: List[str], metadata: Dict):
#         """文件处理完成回调"""
#         # 如果处理成功且生成了新文件，将新文件加入处理队列
#         if result == ProcessResult.SUCCESS and output_files:
#             for output_file in output_files:
#                 new_event = FileEvent(
#                     output_file,
#                     event_type="processor_output",
#                     source_processor=processor.name,
#                     metadata=metadata
#                 )
#
#                 # 检查是否有其他处理器可以处理这个新文件
#                 applicable_processors = self.processor_registry.get_applicable_processors(new_event)
#                 if applicable_processors:
#                     self.task_queue.put(new_event)
#                     logger.debug(f"新生成文件已加入队列: {Path(output_file).name}")
#
#     def get_system_status(self) -> Dict:
#         """获取系统状态"""
#         return {
#             'running': self.running,
#             'queue_size': self.task_queue.qsize(),
#             'worker_count': len(self.workers),
#             'watch_paths': [str(p) for p in self.watch_paths],
#             'processor_statistics': self.processor_registry.get_statistics(),
#             'registered_processors': list(self.processor_registry.get_all_processors().keys())
#         }
#
#
# class PipelineFileHandler(FileSystemEventHandler):
#     """管道文件事件处理器"""
#
#     def __init__(self, task_queue: queue.Queue, processor_registry: ProcessorRegistry):
#         self.task_queue = task_queue
#         self.processor_registry = processor_registry
#         self.logger = logging.getLogger("file_handler")
#
#     def on_created(self, event):
#         if not event.is_directory:
#             self._handle_file_event(event.src_path, "created")
#
#     def on_moved(self, event):
#         if not event.is_directory:
#             self._handle_file_event(event.dest_path, "moved")
#
#     def _handle_file_event(self, file_path: str, event_type: str):
#         """处理文件事件"""
#         try:
#             file_event = FileEvent(file_path, event_type)
#
#             # 等待文件稳定
#             if not self._wait_for_file_stable(file_event.file_path):
#                 return
#
#             # 检查是否有处理器可以处理此文件
#             applicable_processors = self.processor_registry.get_applicable_processors(file_event)
#
#             if applicable_processors:
#                 self.task_queue.put(file_event)
#                 self.logger.info(f"文件已加入处理队列: {file_event.file_path.name} "
#                                  f"(可用处理器: {[p.name for p in applicable_processors]})")
#             else:
#                 self.logger.debug(f"无适用处理器，跳过文件: {file_event.file_path.name}")
#
#         except Exception as e:
#             self.logger.error(f"处理文件事件失败: {e}")
#
#     def _wait_for_file_stable(self, file_path: Path, max_wait: int = 5) -> bool:
#         """等待文件写入完成"""
#         try:
#             if not file_path.exists():
#                 return False
#
#             last_size = -1
#             for _ in range(max_wait):
#                 current_size = file_path.stat().st_size
#                 if current_size == last_size and current_size > 0:
#                     return True
#                 last_size = current_size
#                 time.sleep(0.5)
#
#             return current_size > 0
#         except:
#             return False
#
#
# class PipelineWorker:
#     """管道工作线程"""
#
#     def __init__(self, task_queue: queue.Queue, processor_registry: ProcessorRegistry,
#                  event_manager: PipelineEventManager, completion_callback: Callable):
#         self.task_queue = task_queue
#         self.processor_registry = processor_registry
#         self.event_manager = event_manager
#         self.completion_callback = completion_callback
#         self.running = True
#         self.logger = logging.getLogger("pipeline_worker")
#
#     def run(self):
#         """工作线程主循环"""
#         while self.running:
#             try:
#                 # 获取任务
#                 file_event = self.task_queue.get(timeout=1)
#
#                 # 记录开始处理事件
#                 self.event_manager.log_event(file_event, metadata=file_event.metadata)
#
#                 # 获取适用的处理器
#                 applicable_processors = self.processor_registry.get_applicable_processors(file_event)
#
#                 if not applicable_processors:
#                     self.logger.debug(f"无适用处理器: {file_event.file_path.name}")
#                     self.task_queue.task_done()
#                     continue
#
#                 # 依次执行所有适用的处理器
#                 for processor in applicable_processors:
#                     try:
#                         # 检查是否已被此处理器成功处理过
#                         if self.event_manager.is_file_processed_successfully(
#                                 str(file_event.file_path), processor.name, file_event.file_hash):
#                             self.logger.info(
#                                 f"文件 {file_event.file_path.name} 已被处理器 {processor.name} 处理过，跳过")
#                             processor.update_statistics(ProcessResult.SKIPPED)
#                             continue
#
#                         self.logger.info(f"开始处理 {file_event.file_path.name} (处理器: {processor.name})")
#
#                         # 执行处理
#                         # 获取或创建事件循环
#                         try:
#                             loop = asyncio.get_event_loop()
#                         except RuntimeError:
#                             loop = asyncio.new_event_loop()
#                             asyncio.set_event_loop(loop)
#
#                         result, output_files, metadata = loop.run_until_complete(processor.process(file_event))
#                         pending = asyncio.all_tasks(loop)
#                         if pending:
#                             logger.info(f"⏳ 等待 {len(pending)} 个剩余任务完成...")
#                             loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
#                         # result, output_files, metadata = await processor.process(file_event)
#
#                         # 更新处理器统计
#                         processor.update_statistics(result)
#
#                         # 记录处理结果
#                         self.event_manager.log_event(
#                             file_event, processor.name, result, output_files, metadata
#                         )
#
#                         # 调用完成回调
#                         if self.completion_callback:
#                             self.completion_callback(file_event, processor, result, output_files or [], metadata)
#
#                         self.logger.info(f"处理完成: {processor.name} -> {result.value}")
#
#                     except Exception as e:
#                         self.logger.error(f"处理器 {processor.name} 执行失败: {e}")
#                         processor.update_statistics(ProcessResult.FAILED)
#                         self.event_manager.log_event(
#                             file_event, processor.name, ProcessResult.FAILED,
#                             metadata={"error": str(e)}
#                         )
#
#                 self.task_queue.task_done()
#
#             except queue.Empty:
#                 continue
#             except Exception as e:
#                 self.logger.error(f"工作线程异常: {e}")
#
#     def stop(self):
#         """停止工作线程"""
#         self.running = False
#
#
# def main():
#     """主函数示例"""
#     # 配置
#     config = {
#         'worker_count': 3,
#         'queue_size': 100
#     }
#
#     # 创建管道系统
#     pipeline = FilePipelineSystem(
#         watch_paths=["./input", "./output/transcripts"],  # 监控多个目录
#         config=config
#     )
#
#     # 注册处理器
#
#     # 1. 语音转文字处理器
#     audio_processor = AudioToTextProcessor({
#         'output_dir': './output/transcripts',
#         'language': 'zh-CN',
#         'model': 'whisper-large'
#     })
#     pipeline.register_processor(audio_processor)
#
#     # 2. 知识库加工处理器
#     knowledge_processor = KnowledgeProcessor({
#         'output_dir': './output/knowledge',
#         'enable_summary': True,
#         'enable_keywords': True,
#         'enable_entities': True,
#         'max_keywords': 20
#     })
#     pipeline.register_processor(knowledge_processor)
#
#     try:
#         # 启动管道系统
#         pipeline.start()
#
#         # 打印启动信息
#         logger.info("=" * 60)
#         logger.info("文件处理管道系统已启动")
#         logger.info("=" * 60)
#
#         # 显示系统状态
#         status = pipeline.get_system_status()
#         logger.info(f"监控目录: {', '.join(status['watch_paths'])}")
#         logger.info(f"工作线程数: {status['worker_count']}")
#         logger.info(f"已注册处理器: {', '.join(status['registered_processors'])}")
#
#         # 创建输入目录（如果不存在）
#         for watch_path in pipeline.watch_paths:
#             watch_path.mkdir(parents=True, exist_ok=True)
#             logger.info(f"监控目录已准备: {watch_path}")
#
#         logger.info("=" * 60)
#         logger.info("系统运行中... 请将文件放入监控目录")
#         logger.info("支持的音频格式: .wav, .mp3, .m4a, .flac, .aac")
#         logger.info("支持的文本格式: .txt, .md")
#         logger.info("按 Ctrl+C 停止系统")
#         logger.info("=" * 60)
#
#         # 定期显示系统状态
#         status_interval = 30  # 每30秒显示一次状态
#         last_status_time = time.time()
#
#         while True:
#             time.sleep(1)
#
#             # 定期显示状态信息
#             current_time = time.time()
#             if current_time - last_status_time >= status_interval:
#                 status = pipeline.get_system_status()
#                 stats = status['processor_statistics']
#
#                 logger.info("=" * 40)
#                 logger.info("系统状态报告:")
#                 logger.info(f"队列中任务数: {status['queue_size']}")
#
#                 for processor_name, processor_stats in stats.items():
#                     logger.info(f"处理器 [{processor_name}]:")
#                     logger.info(f"  已处理: {processor_stats['processed']} 个文件")
#                     logger.info(f"  成功: {processor_stats['success']} | "
#                                 f"失败: {processor_stats['failed']} | "
#                                 f"跳过: {processor_stats['skipped']}")
#
#                 logger.info("=" * 40)
#                 last_status_time = current_time
#
#     except KeyboardInterrupt:
#         logger.info("\n收到停止信号，正在关闭系统...")
#
#     except Exception as e:
#         logger.error(f"系统运行异常: {e}")
#
#     finally:
#         # 停止管道系统
#         pipeline.stop()
#
#         # 显示最终统计
#         final_status = pipeline.get_system_status()
#         final_stats = final_status['processor_statistics']
#
#         logger.info("=" * 60)
#         logger.info("系统已关闭 - 最终统计报告:")
#         logger.info("=" * 60)
#
#         total_processed = 0
#         total_success = 0
#         total_failed = 0
#
#         for processor_name, stats in final_stats.items():
#             logger.info(f"处理器 [{processor_name}]:")
#             logger.info(f"  总处理数: {stats['processed']}")
#             logger.info(f"  成功: {stats['success']}")
#             logger.info(f"  失败: {stats['failed']}")
#             logger.info(f"  跳过: {stats['skipped']}")
#             logger.info(f"  成功率: {stats['success'] / max(stats['processed'], 1) * 100:.1f}%")
#             logger.info("-" * 30)
#
#             total_processed += stats['processed']
#             total_success += stats['success']
#             total_failed += stats['failed']
#
#         logger.info(f"系统总计:")
#         logger.info(f"  总处理数: {total_processed}")
#         logger.info(f"  总成功数: {total_success}")
#         logger.info(f"  总失败数: {total_failed}")
#         logger.info(f"  整体成功率: {total_success / max(total_processed, 1) * 100:.1f}%")
#         logger.info("=" * 60)
#         logger.info("感谢使用文件处理管道系统!")
#
#
# def create_sample_files():
#     """创建示例文件用于测试"""
#     import os
#
#     # 确保输入目录存在
#     input_dir = Path("./input")
#     input_dir.mkdir(exist_ok=True)
#
#     # 创建示例文本文件
#     sample_text = """这是一个示例文本文件，用于测试知识库加工处理器。
#
# 内容包括：
# 1. 产品介绍：我们的智能客服系统能够自动处理用户咨询
# 2. 技术特点：使用了先进的自然语言处理技术
# 3. 应用场景：适用于电商、金融、教育等多个行业
#
# 联系方式：
# 电话：400-123-4567
# 邮箱：support@example.com
#
# 本文档最后更新时间：2024年12月"""
#
#     sample_file = input_dir / "sample_text.txt"
#     with open(sample_file, 'w', encoding='utf-8') as f:
#         f.write(sample_text)
#
#     logger.info(f"已创建示例文件: {sample_file}")
#
#     # 创建示例 Markdown 文件
#     sample_md = """# 产品使用手册
#
# ## 功能概述
# 本系统提供完整的文件处理解决方案。
#
# ## 主要特性
# - **语音转文字**: 支持多种音频格式
# - **知识加工**: 自动提取关键信息
# - **实时监控**: 自动处理新增文件
#
# ## 使用流程
# 1. 将文件放入监控目录
# 2. 系统自动识别并处理
# 3. 查看输出结果
#
# > 注意：请确保文件格式正确
# """
#
#     sample_md_file = input_dir / "manual.md"
#     with open(sample_md_file, 'w', encoding='utf-8') as f:
#         f.write(sample_md)
#
#     logger.info(f"已创建示例 Markdown 文件: {sample_md_file}")
#
#
# if __name__ == "__main__":
#     # 设置控制台日志格式
#     console_handler = logging.StreamHandler()
#     console_handler.setLevel(logging.INFO)
#     formatter = logging.Formatter(
#         '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#         datefmt='%H:%M:%S'
#     )
#     console_handler.setFormatter(formatter)
#
#     # 获取根日志记录器并配置
#     root_logger = logging.getLogger()
#     root_logger.handlers.clear()
#     root_logger.addHandler(console_handler)
#     root_logger.setLevel(logging.INFO)
#
#     # 显示启动横幅
#     print("=" * 80)
#     print("          文件处理管道系统 v1.1")
#     print("        模块化 • 可扩展 • 高效能")
#     print("        支持启动时扫描现有文件")
#     print("=" * 80)
#     print()
#
#     # 询问是否创建示例文件
#     try:
#         create_samples = input("是否创建示例文件用于测试? (y/N): ").lower().strip()
#         if create_samples in ['y', 'yes']:
#             create_sample_files()
#             print()
#     except (EOFError, KeyboardInterrupt):
#         print("\n跳过示例文件创建")
#
#     # 启动主程序
#     main()