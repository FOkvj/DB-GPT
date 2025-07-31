#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于消息队列的文件处理系统
将原有的文件监控模式改为消息队列消费模式
"""
import asyncio
import io
import logging
import os
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any

from dbgpt._private.config import Config
from dbgpt.component import ComponentType, BaseComponent, SystemApp
from dbgpt.core.interface.file import FileStorageClient
from dbgpt.rag.knowledge.base import KnowledgeType, DocumentType
from dbgpt_app.expend.dao.file_process_dao import FileProcessingRequest, FileProcessingDao, SourceType, ProcessStatus
from dbgpt_app.expend.dao.knowledge_mapping_dao import KnowledgeBaseMappingDao, KnowledgeBaseMappingDaoResponse
from dbgpt_app.expend.model.file_process import FileBucket, ProcessTopic

from dbgpt_app.expend.service.queue.mq import MessageQueueManagerInterface, RabbitMQManager
from dbgpt_app.expend.service.speech2text import Speech2TextService
from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest, KnowledgeDocumentRequest
from dbgpt_app.knowledge.service import KnowledgeService
from dbgpt_ext.rag import ChunkParameters
from dbgpt_serve.rag.api.schemas import KnowledgeSyncRequest
from dbgpt_serve.rag.service.service import Service

CFG = Config()
logger = logging.getLogger(__name__)


class ProcessResult(Enum):
    """处理结果状态"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


class MessageQueueProcessorInterface(ABC):
    """消息队列处理器接口基类"""

    def __init__(self, name: str, topic: str, mq_manager: MessageQueueManagerInterface, config: Dict = None):
        self.name = name
        self.topic = topic
        self.mq_manager = mq_manager
        self.config = config or {}
        self.logger = logging.getLogger(f"processor.{name}")
        self.enabled = True
        self.consumer = None

    @abstractmethod
    async def process_message(self, file_meta: FileProcessingRequest) -> None:
        """
        处理消息
        不返回任何值，直接处理文件并更新状态
        """
        pass

    @abstractmethod
    def can_process(self, file_meta: FileProcessingRequest) -> bool:
        """判断是否可以处理此文件"""
        pass

    def start_consuming(self):
        """开始消费消息"""
        try:
            self.consumer = self.mq_manager.subscribe_point_to_point(
                self.topic,
                self._message_callback,
                consumer_id=f"{self.name}_consumer"
            )
            self.logger.info(f"处理器 {self.name} 开始消费主题: {self.topic}")
        except Exception as e:
            self.logger.error(f"启动消费者失败: {e}")

    def stop_consuming(self):
        """停止消费消息"""
        if self.consumer:
            try:
                self.consumer.stop_consuming()
                self.consumer.disconnect()
                self.logger.info(f"处理器 {self.name} 停止消费")
            except Exception as e:
                self.logger.error(f"停止消费者失败: {e}")

    def _message_callback(self, message_data: Any):
        """消息回调处理"""
        try:
            # 解析消息数据
            if isinstance(message_data, dict):
                file_meta = FileProcessingRequest(**message_data)
            else:
                file_meta = message_data

            self.logger.info(f"收到消息: {file_meta.file_name}")

            # 检查是否可以处理
            if not self.can_process(file_meta):
                self.logger.info(f"跳过文件 {file_meta.file_name}")
                return


            # 创建事件循环处理异步任务
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # 处理消息
            loop.run_until_complete(self.process_message(file_meta))
            pending = asyncio.all_tasks(loop)
            if pending:
                logger.info(f"⏳ 等待 {len(pending)} 个剩余任务完成...")
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        except Exception as e:
            self.logger.error(f"处理消息失败: {e}")


    def _get_next_topic(self, file_meta: FileProcessingRequest) -> Optional[str]:
        """获取下一个处理主题"""
        # 音频转文字后发送到知识库处理
        if self.name == "audio_to_text":
            return "to_knowledge"
        return None



class AudioToTextProcessor(MessageQueueProcessorInterface):
    """语音转文字处理器 - 消息队列版本"""

    def __init__(self, transcriber: Speech2TextService, mq_manager: MessageQueueManagerInterface, config: Dict = None):
        super().__init__("audio_to_text", ProcessTopic.STT.value, mq_manager, config)
        self.supported_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg', '.wma', '.opus', '.aiff', '.au']
        self.transcriber = transcriber
        self._transcriber_lock = threading.Lock()
        self.file_process_dao = FileProcessingDao()

    def can_process(self, file_meta: FileProcessingRequest) -> bool:
        """检查是否可以处理音频文件"""
        if not self.enabled:
            return False

        # 检查文件扩展名
        file_ext = Path(file_meta.file_name).suffix.lower()
        if file_ext not in self.supported_extensions:
            return False

        # 只处理来自FTP等外部源的文件
        if file_meta.source_type != SourceType.FTP:
            return False

        return True

    async def process_message(self, file_meta: FileProcessingRequest) -> None:
        """处理语音转文字"""
        try:
            self.logger.info(f"开始语音转文字: {file_meta.file_name}")
            fs: FileStorageClient = FileStorageClient.get_instance(CFG.SYSTEM_APP, default_component=None)

            # 更新处理状态
            self.file_process_dao.update_file_processing_by_file_id(
                file_meta.file_id,
                status=ProcessStatus.PROCESSING.value,
                start_time=datetime.now()
            )

            # 从文件存储系统获取文件
            tmp_dir = tempfile.mkdtemp()
            tmp_path = os.path.join(tmp_dir, file_meta.file_name)
            # target_path, meta = fs.download_file(file_meta.file_id, tmp_path)
            bio_data, meta = fs.get_file(file_meta.file_id)
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = bio_data.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            # 执行语音转文字
            with self._transcriber_lock:
                transcription_result = await self.transcriber.transcribe_file(
                    audio_file_path=tmp_path,
                    threshold=0.5
                )

            # 提取转写结果
            transcript_text = transcription_result.data['transcript']

            # 生成转写文件名
            transcript_filename = f"{Path(file_meta.file_name).stem}_transcript.txt"

            # 将转写结果上传到文件存储系统
            transcript_file_obj = io.BytesIO(transcript_text.encode('utf-8'))

            transcript_bucket = FileBucket.TO_KONWLEDGE.value
            transcript_file_id = fs.save_file(
                bucket=transcript_bucket,
                file_name=transcript_filename,
                file_data=transcript_file_obj
            )

            # 清理临时文件
            try:
                Path(tmp_path).unlink()
            except:
                pass

            # 创建新的文件元数据
            new_file_meta = FileProcessingRequest(
                file_id=transcript_file_id,
                file_name=transcript_filename,
                source_type=SourceType.STT.value,
                source_id=f"audio_processor",
                size=len(transcript_text.encode('utf-8')),
                file_type='.txt',
                file_hash=self._calculate_hash(transcript_text),
                status=ProcessStatus.WAIT,
                start_time=datetime.now()
            )

            # 将新文件信息写入数据库
            self.file_process_dao.create(new_file_meta)

            # 更新原文件处理状态
            self.file_process_dao.update_file_processing_by_file_id(
                file_meta.file_id,
                status=ProcessStatus.SUCCESS.value,
                end_time=datetime.now()
            )

            # 发送新文件到knowledge处理队列
            self.mq_manager.publish_point_to_point(ProcessTopic.TO_KNOWLEDGE.value, new_file_meta.dict())

            self.logger.info(f"语音转文字完成: {transcript_filename}")

        except Exception as e:
            self.logger.error(f"语音转文字失败: {e}")
            # 更新失败状态
            self.file_process_dao.update_file_processing_by_file_id(
                file_meta.file_id,
                status=ProcessStatus.FAILED.value,
                end_time=datetime.now()
            )
            raise

    def _calculate_hash(self, text: str) -> str:
        """计算文本哈希"""
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()


class KnowledgeProcessor(MessageQueueProcessorInterface):
    """知识库处理器 - 消息队列版本"""

    def __init__(self, mq_manager: MessageQueueManagerInterface, config: Dict = None):
        super().__init__("knowledge_processor", "to_knowledge", mq_manager, config)
        self.supported_extensions = ['.txt', '.md', '.csv', '.pdf', '.xlsx', '.doc', '.docx']
        self.knowledge_space_service = KnowledgeService()
        self.fs = FileStorageClient.get_instance(CFG.SYSTEM_APP, default_component=None)
        self.file_process_dao = FileProcessingDao()
        self.knowledge_mapping_dao = KnowledgeBaseMappingDao()

    def can_process(self, file_meta: FileProcessingRequest) -> bool:
        """检查是否可以处理文档文件"""
        if not self.enabled:
            return False

        # 检查文件扩展名
        file_ext = Path(file_meta.file_name).suffix.lower()
        if file_ext not in self.supported_extensions:
            return False

        return True

    def _create_space(self, space_name: str):
        """创建知识库空间"""
        try:
            self.logger.info(f"创建知识库: {space_name}")
            request = KnowledgeSpaceRequest(
                name=space_name,
                desc=f"自动生成的知识库: {space_name}",
                vector_type="VectorStore",
                domain_type="Normal",
            )
            self.knowledge_space_service.create_knowledge_space(request)
        except Exception as e:
            # 如果空间已存在，忽略错误
            if "already exists" not in str(e).lower():
                raise

    def _create_knowledge_doc(self, file_meta: FileProcessingRequest, space_name: str):
        """上传文件到知识库"""
        self.logger.info(f"上传文件到知识库: {file_meta.file_name}")

        # 创建知识库文档
        request = KnowledgeDocumentRequest()
        request.doc_name = file_meta.file_name
        request.doc_type = KnowledgeType.DOCUMENT.name
        request.content = file_meta.file_id

        result = self.knowledge_space_service.create_knowledge_document(
            space=space_name,
            request=request
        )
        return result

    async def _sync_doc(self, space_name: str, doc_id: int):
        """同步文档到向量数据库"""
        self.logger.info(f"开始同步文档: {space_name}, {doc_id}")
        service = Service.get_instance(CFG.SYSTEM_APP)

        try:
            space = service.get({"name": space_name})
            if space is None:
                raise ValueError(f"knowledge_space {space_name} can not be found")

            sync_request = KnowledgeSyncRequest(
                doc_id=doc_id,
                space_id=str(space.id),
                chunk_parameters=ChunkParameters(
                    chunk_strategy="Automatic",
                    chunk_size=512,
                    chunk_overlap=50,
                )
            )
            doc_ids = await service.sync_document(requests=[sync_request])
            return doc_ids
        except Exception as e:
            self.logger.error(f"Failed to sync document: {e}")
            raise

    async def process_message(self, file_meta: FileProcessingRequest) -> None:
        """处理知识库加工"""
        try:
            mapping: KnowledgeBaseMappingDaoResponse = self.knowledge_mapping_dao.get_mapping_by_scan_config_name(file_meta.source_id)
            # 生成知识库空间名
            space_name = file_meta.file_name if mapping is None else mapping.knowledge_base_name
            if mapping is None:
                self._create_space(space_name)

            self.logger.info(f"开始知识库加工: {space_name}")

            # 更新处理状态
            self.file_process_dao.update_file_processing_by_file_id(
                file_meta.file_id,
                status=ProcessStatus.PROCESSING.value,
                start_time=datetime.now()
            )



            # 创建请求
            doc_id = self._create_knowledge_doc(file_meta, space_name)

            # 同步文档
            doc_ids = await self._sync_doc(space_name=space_name, doc_id=doc_id)

            # 更新处理状态
            self.file_process_dao.update_file_processing_by_file_id(
                file_meta.file_id,
                status=ProcessStatus.SUCCESS.value,
                end_time=datetime.now()
            )

            self.logger.info(f"知识库加工完成: {space_name}")

        except Exception as e:
            self.logger.error(f"知识库加工失败: {e}")
            # 更新失败状态
            self.file_process_dao.update_file_processing_by_file_id(
                file_meta.file_id,
                status=ProcessStatus.FAILED.value,
                end_time=datetime.now()
            )
            raise


class MessageQueueProcessorManager(BaseComponent):
    """消息队列处理器管理器"""
    name = ComponentType.QUEUE_PROCESSOR_MANAGER

    def __init__(self, mq_manager: MessageQueueManagerInterface, **kwargs):
        super().__init__(**kwargs)
        self.mq_manager = mq_manager
        self.processors: Dict[str, MessageQueueProcessorInterface] = {}
        self.logger = logging.getLogger("mq_processor_manager")

    def init_app(self, system_app: SystemApp):
        pass

    def register_processor(self, processor: MessageQueueProcessorInterface):
        """注册处理器"""
        self.processors[processor.name] = processor
        self.logger.info(f"已注册处理器: {processor.name} -> 主题: {processor.topic}")

    def start_all_processors(self):
        """启动所有处理器"""
        for name, processor in self.processors.items():
            try:
                processor.start_consuming()
                self.logger.info(f"处理器 {name} 已启动")
            except Exception as e:
                self.logger.error(f"启动处理器 {name} 失败: {e}")

    def stop_all_processors(self):
        """停止所有处理器"""
        for name, processor in self.processors.items():
            try:
                processor.stop_consuming()
                self.logger.info(f"处理器 {name} 已停止")
            except Exception as e:
                self.logger.error(f"停止处理器 {name} 失败: {e}")


    def get_processor(self, name: str) -> Optional[MessageQueueProcessorInterface]:
        """获取指定处理器"""
        return self.processors.get(name)


def main():
    """主函数示例"""
    # 初始化消息队列管理器
    mq_manager = RabbitMQManager(
        host='localhost',
        port=5672,
        username='guest',
        password='guest'
    )

    # 创建处理器管理器
    processor_manager = MessageQueueProcessorManager(mq_manager)

    # 获取语音转文字服务
    voice2text_service = CFG.SYSTEM_APP.get_component(
        ComponentType.SPEECH_TO_TEXT,
        Speech2TextService
    )

    # 注册语音转文字处理器
    audio_processor = AudioToTextProcessor(
        transcriber=voice2text_service,
        mq_manager=mq_manager,
        config={'output_bucket': 'transcripts'}
    )
    processor_manager.register_processor(audio_processor)

    # 注册知识库处理器
    knowledge_processor = KnowledgeProcessor(
        mq_manager=mq_manager,
        config={'enable_summary': True}
    )
    processor_manager.register_processor(knowledge_processor)

    try:
        # 启动所有处理器
        processor_manager.start_all_processors()

        logger.info("=" * 60)
        logger.info("消息队列文件处理系统已启动")
        logger.info("=" * 60)
        logger.info("已注册的处理器:")
        for name, processor in processor_manager.processors.items():
            logger.info(f"  - {name}: 主题 {processor.topic}")
        logger.info("=" * 60)
        logger.info("系统运行中... 按 Ctrl+C 停止")



    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在关闭系统...")
    except Exception as e:
        logger.error(f"系统运行异常: {e}")
    finally:
        # 停止所有处理器
        processor_manager.stop_all_processors()

        # 关闭消息队列连接
        mq_manager.shutdown()

        logger.info("系统已关闭")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    main()