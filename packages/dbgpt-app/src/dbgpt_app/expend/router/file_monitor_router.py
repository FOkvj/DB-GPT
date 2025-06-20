#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块化文件处理管道系统
支持插件化的处理器架构，实现解耦和可扩展性
"""

import os
import time
import threading
import queue
import logging
import sqlite3
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any, Tuple
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessResult(Enum):
    """处理结果状态"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


class FileEvent:
    """文件事件对象"""

    def __init__(self, file_path: str, event_type: str = "created",
                 metadata: Dict = None, source_processor: str = None):
        self.file_path = Path(file_path).absolute()
        self.event_type = event_type
        self.timestamp = datetime.now()
        self.metadata = metadata or {}
        self.source_processor = source_processor  # 产生此文件的处理器
        self.file_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """计算文件哈希"""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
        except:
            pass
        return ""

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'file_path': str(self.file_path),
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'source_processor': self.source_processor,
            'file_hash': self.file_hash
        }


class ProcessorInterface(ABC):
    """处理器接口基类"""

    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"processor.{name}")
        self.enabled = True
        self.statistics = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }

    @abstractmethod
    def can_process(self, file_event: FileEvent) -> bool:
        """判断是否可以处理此文件"""
        pass

    @abstractmethod
    def process(self, file_event: FileEvent) -> Tuple[ProcessResult, Optional[List[str]], Dict]:
        """
        处理文件
        返回: (结果状态, 生成的文件列表, 元数据)
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        pass

    def get_output_directory(self) -> Optional[Path]:
        """获取输出目录"""
        return self.config.get('output_dir')

    def setup(self):
        """初始化设置"""
        output_dir = self.get_output_directory()
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        """清理资源"""
        pass

    def get_statistics(self) -> Dict:
        """获取处理统计"""
        return self.statistics.copy()

    def update_statistics(self, result: ProcessResult):
        """更新统计信息"""
        self.statistics['processed'] += 1
        if result == ProcessResult.SUCCESS:
            self.statistics['success'] += 1
        elif result == ProcessResult.FAILED:
            self.statistics['failed'] += 1
        elif result == ProcessResult.SKIPPED:
            self.statistics['skipped'] += 1


class AudioToTextProcessor(ProcessorInterface):
    """语音转文字处理器"""

    def __init__(self, config: Dict = None):
        super().__init__("audio_to_text", config)
        self.supported_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.aac']

    def can_process(self, file_event: FileEvent) -> bool:
        """检查是否可以处理音频文件"""
        if not self.enabled:
            return False

        # 检查文件扩展名
        if file_event.file_path.suffix.lower() not in self.supported_extensions:
            return False

        # 避免处理由其他处理器生成的文件
        if file_event.source_processor:
            return False

        return True

    def process(self, file_event: FileEvent) -> Tuple[ProcessResult, Optional[List[str]], Dict]:
        """执行语音转文字"""
        try:
            self.logger.info(f"开始语音转文字: {file_event.file_path.name}")

            # 检查文件是否存在且不为空
            if not file_event.file_path.exists() or file_event.file_path.stat().st_size == 0:
                return ProcessResult.FAILED, None, {"error": "文件不存在或为空"}

            # 生成输出文件路径
            output_dir = Path(self.get_output_directory() or "./output/transcripts")
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / f"{file_event.file_path.stem}_transcript.txt"

            # TODO: 集成实际的语音转文字引擎
            # 这里使用占位实现
            transcript_text = self._mock_speech_to_text(file_event.file_path)

            # 写入转换结果
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcript_text)

            # 准备元数据
            metadata = {
                'original_file': str(file_event.file_path),
                'processor': self.name,
                'processing_time': datetime.now().isoformat(),
                'file_size': file_event.file_path.stat().st_size,
                'transcript_length': len(transcript_text),
                'language': self.config.get('language', 'auto'),
                'model': self.config.get('model', 'default')
            }

            self.logger.info(f"语音转文字完成: {output_file.name}")
            return ProcessResult.SUCCESS, [str(output_file)], metadata

        except Exception as e:
            self.logger.error(f"语音转文字失败: {e}")
            return ProcessResult.FAILED, None, {"error": str(e)}

    def _mock_speech_to_text(self, audio_file: Path) -> str:
        """模拟语音转文字（替换为实际的ASR引擎）"""
        # 模拟处理时间
        time.sleep(2)

        # 返回模拟的转录文本
        return f"""这是文件 {audio_file.name} 的语音转文字结果。

时间戳: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
文件大小: {audio_file.stat().st_size} 字节

在实际应用中，这里应该是真实的语音识别结果。
可以集成如 OpenAI Whisper、Azure Speech、Google Speech-to-Text 等服务。

示例转录内容：
用户: 你好，我想了解一下产品的具体功能。
客服: 好的，我来为您详细介绍...

[转录结束]
"""

    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions


class KnowledgeProcessor(ProcessorInterface):
    """知识库加工处理器"""

    def __init__(self, config: Dict = None):
        super().__init__("knowledge_processor", config)
        self.supported_extensions = ['.txt', '.md']

    def can_process(self, file_event: FileEvent) -> bool:
        """检查是否可以处理文本文件"""
        if not self.enabled:
            return False

        # 只处理文本文件
        if file_event.file_path.suffix.lower() not in self.supported_extensions:
            return False

        # 优先处理来自语音转文字的结果
        if (file_event.source_processor == "audio_to_text" or
                "_transcript" in file_event.file_path.name):
            return True

        # 也可以处理其他文本文件
        return file_event.source_processor is None

    def process(self, file_event: FileEvent) -> Tuple[ProcessResult, Optional[List[str]], Dict]:
        """执行知识加工"""
        try:
            self.logger.info(f"开始知识加工: {file_event.file_path.name}")

            # 读取文本内容
            with open(file_event.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                return ProcessResult.SKIPPED, None, {"reason": "文件内容为空"}

            # 生成输出目录
            output_dir = Path(self.get_output_directory() or "./output/knowledge")
            output_dir.mkdir(parents=True, exist_ok=True)

            # 执行知识加工
            processed_results = self._process_knowledge(content, file_event)

            # 生成输出文件
            output_files = []
            base_name = file_event.file_path.stem

            # 生成结构化知识文件
            if processed_results.get('structured_content'):
                structured_file = output_dir / f"{base_name}_structured.json"
                with open(structured_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_results['structured_content'], f,
                              ensure_ascii=False, indent=2)
                output_files.append(str(structured_file))

            # 生成摘要文件
            if processed_results.get('summary'):
                summary_file = output_dir / f"{base_name}_summary.txt"
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(processed_results['summary'])
                output_files.append(str(summary_file))

            # 生成关键词文件
            if processed_results.get('keywords'):
                keywords_file = output_dir / f"{base_name}_keywords.txt"
                with open(keywords_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(processed_results['keywords']))
                output_files.append(str(keywords_file))

            metadata = {
                'original_file': str(file_event.file_path),
                'processor': self.name,
                'processing_time': datetime.now().isoformat(),
                'content_length': len(content),
                'keywords_count': len(processed_results.get('keywords', [])),
                'entities_count': len(processed_results.get('structured_content', {}).get('entities', [])),
                'source_processor': file_event.source_processor
            }

            self.logger.info(f"知识加工完成: 生成 {len(output_files)} 个文件")
            return ProcessResult.SUCCESS, output_files, metadata

        except Exception as e:
            self.logger.error(f"知识加工失败: {e}")
            return ProcessResult.FAILED, None, {"error": str(e)}

    def _process_knowledge(self, content: str, file_event: FileEvent) -> Dict:
        """执行知识加工逻辑"""
        # 模拟处理时间
        time.sleep(1)

        # TODO: 集成实际的NLP处理引擎
        # 这里是示例实现

        # 简单的关键词提取
        keywords = self._extract_keywords(content)

        # 生成摘要
        summary = self._generate_summary(content)

        # 结构化内容
        structured_content = {
            'title': f"知识加工结果 - {file_event.file_path.stem}",
            'source': str(file_event.file_path),
            'content_type': 'transcript' if file_event.source_processor == 'audio_to_text' else 'text',
            'entities': self._extract_entities(content),
            'topics': self._extract_topics(content),
            'metadata': {
                'processed_at': datetime.now().isoformat(),
                'word_count': len(content.split()),
                'char_count': len(content)
            }
        }

        return {
            'keywords': keywords,
            'summary': summary,
            'structured_content': structured_content
        }

    def _extract_keywords(self, content: str) -> List[str]:
        """简单的关键词提取"""
        # 这里应该使用实际的NLP库如jieba、spaCy等
        words = content.replace('，', ' ').replace('。', ' ').replace('\n', ' ').split()
        # 简单筛选长度大于2的词
        keywords = list(set([word for word in words if len(word) > 2]))[:10]
        return keywords

    def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        # 简单实现：取前200字符
        summary = content.strip()[:200]
        if len(content) > 200:
            summary += "..."
        return f"摘要：\n{summary}\n\n[此摘要由系统自动生成]"

    def _extract_entities(self, content: str) -> List[Dict]:
        """提取实体"""
        # 简单实现：查找常见实体模式
        entities = []
        # 这里应该使用NER模型
        if "时间" in content:
            entities.append({"type": "TIME", "text": "时间相关"})
        if any(word in content for word in ["产品", "服务", "功能"]):
            entities.append({"type": "PRODUCT", "text": "产品相关"})
        return entities

    def _extract_topics(self, content: str) -> List[str]:
        """提取主题"""
        topics = []
        if "客服" in content or "咨询" in content:
            topics.append("客户服务")
        if "产品" in content:
            topics.append("产品介绍")
        return topics or ["通用"]

    def get_supported_extensions(self) -> List[str]:
        return self.supported_extensions


class ProcessorRegistry:
    """处理器注册中心"""

    def __init__(self):
        self.processors: Dict[str, ProcessorInterface] = {}
        self.logger = logging.getLogger("processor_registry")

    def register(self, processor: ProcessorInterface):
        """注册处理器"""
        self.processors[processor.name] = processor
        processor.setup()
        self.logger.info(f"已注册处理器: {processor.name}")

    def unregister(self, name: str):
        """注销处理器"""
        if name in self.processors:
            self.processors[name].cleanup()
            del self.processors[name]
            self.logger.info(f"已注销处理器: {name}")

    def get_applicable_processors(self, file_event: FileEvent) -> List[ProcessorInterface]:
        """获取可处理指定文件的处理器"""
        applicable = []
        for processor in self.processors.values():
            if processor.can_process(file_event):
                applicable.append(processor)
        return applicable

    def get_all_processors(self) -> Dict[str, ProcessorInterface]:
        """获取所有处理器"""
        return self.processors.copy()

    def get_statistics(self) -> Dict:
        """获取所有处理器的统计信息"""
        stats = {}
        for name, processor in self.processors.items():
            stats[name] = processor.get_statistics()
        return stats


class PipelineEventManager:
    """管道事件管理器"""

    def __init__(self, db_path: str = "./pipeline_events.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        self.init_database()

    def init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    processor_name TEXT,
                    result TEXT,
                    metadata TEXT,
                    created_time TEXT NOT NULL,
                    output_files TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON pipeline_events(file_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_processor ON pipeline_events(processor_name)")

    def log_event(self, file_event: FileEvent, processor_name: str = None,
                  result: ProcessResult = None, output_files: List[str] = None,
                  metadata: Dict = None):
        """记录管道事件"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO pipeline_events 
                        (file_path, event_type, processor_name, result, metadata, created_time, output_files)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(file_event.file_path),
                        file_event.event_type,
                        processor_name,
                        result.value if result else None,
                        json.dumps(metadata or {}),
                        file_event.timestamp.isoformat(),
                        json.dumps(output_files or [])
                    ))
        except Exception as e:
            logger.error(f"记录事件失败: {e}")

    def get_file_processing_history(self, file_path: str) -> List[Dict]:
        """获取文件的处理历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM pipeline_events 
                    WHERE file_path = ? 
                    ORDER BY created_time
                """, (str(Path(file_path).absolute()),))

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取处理历史失败: {e}")
            return []


class FilePipelineSystem:
    """文件处理管道系统"""

    def __init__(self, watch_paths: List[str], config: Dict = None):
        self.watch_paths = [Path(p) for p in watch_paths]
        self.config = config or {}
        self.processor_registry = ProcessorRegistry()
        self.event_manager = PipelineEventManager()
        self.task_queue = queue.Queue(maxsize=self.config.get('queue_size', 1000))
        self.workers = []
        self.observer = None
        self.running = False

        # 确保监控目录存在
        for path in self.watch_paths:
            path.mkdir(parents=True, exist_ok=True)

    def register_processor(self, processor: ProcessorInterface):
        """注册处理器"""
        self.processor_registry.register(processor)

    def start(self):
        """启动管道系统"""
        logger.info("启动文件处理管道系统...")

        # 启动工作线程
        self._start_workers()

        # 启动文件监控
        self._start_file_monitoring()

        self.running = True
        logger.info(f"系统已启动，监控路径: {[str(p) for p in self.watch_paths]}")

        # 显示已注册的处理器
        processors = self.processor_registry.get_all_processors()
        logger.info(f"已注册处理器: {list(processors.keys())}")

    def stop(self):
        """停止管道系统"""
        logger.info("正在停止管道系统...")

        self.running = False

        # 停止文件监控
        if self.observer:
            self.observer.stop()
            self.observer.join()

        # 等待队列处理完成
        self.task_queue.join()

        # 停止工作线程
        for worker in self.workers:
            worker.stop()

        # 清理处理器资源
        for processor in self.processor_registry.get_all_processors().values():
            processor.cleanup()

        logger.info("管道系统已停止")

    def _start_workers(self):
        """启动工作线程"""
        worker_count = self.config.get('worker_count', 3)

        for i in range(worker_count):
            worker = PipelineWorker(
                self.task_queue,
                self.processor_registry,
                self.event_manager,
                self._on_file_processed
            )
            thread = threading.Thread(target=worker.run, name=f"PipelineWorker-{i + 1}")
            thread.daemon = True
            thread.start()
            self.workers.append(worker)

        logger.info(f"已启动 {worker_count} 个工作线程")

    def _start_file_monitoring(self):
        """启动文件监控"""
        event_handler = PipelineFileHandler(self.task_queue, self.processor_registry)
        self.observer = Observer()

        for watch_path in self.watch_paths:
            self.observer.schedule(event_handler, str(watch_path), recursive=True)

        self.observer.start()
        logger.info("文件监控已启动")

    def _on_file_processed(self, file_event: FileEvent, processor: ProcessorInterface,
                           result: ProcessResult, output_files: List[str], metadata: Dict):
        """文件处理完成回调"""
        # 如果处理成功且生成了新文件，将新文件加入处理队列
        if result == ProcessResult.SUCCESS and output_files:
            for output_file in output_files:
                new_event = FileEvent(
                    output_file,
                    event_type="processor_output",
                    source_processor=processor.name,
                    metadata=metadata
                )

                # 检查是否有其他处理器可以处理这个新文件
                applicable_processors = self.processor_registry.get_applicable_processors(new_event)
                if applicable_processors:
                    self.task_queue.put(new_event)
                    logger.debug(f"新生成文件已加入队列: {Path(output_file).name}")

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            'running': self.running,
            'queue_size': self.task_queue.qsize(),
            'worker_count': len(self.workers),
            'watch_paths': [str(p) for p in self.watch_paths],
            'processor_statistics': self.processor_registry.get_statistics(),
            'registered_processors': list(self.processor_registry.get_all_processors().keys())
        }


class PipelineFileHandler(FileSystemEventHandler):
    """管道文件事件处理器"""

    def __init__(self, task_queue: queue.Queue, processor_registry: ProcessorRegistry):
        self.task_queue = task_queue
        self.processor_registry = processor_registry
        self.logger = logging.getLogger("file_handler")

    def on_created(self, event):
        if not event.is_directory:
            self._handle_file_event(event.src_path, "created")

    def on_moved(self, event):
        if not event.is_directory:
            self._handle_file_event(event.dest_path, "moved")

    def _handle_file_event(self, file_path: str, event_type: str):
        """处理文件事件"""
        try:
            file_event = FileEvent(file_path, event_type)

            # 等待文件稳定
            if not self._wait_for_file_stable(file_event.file_path):
                return

            # 检查是否有处理器可以处理此文件
            applicable_processors = self.processor_registry.get_applicable_processors(file_event)

            if applicable_processors:
                self.task_queue.put(file_event)
                self.logger.info(f"文件已加入处理队列: {file_event.file_path.name} "
                                 f"(可用处理器: {[p.name for p in applicable_processors]})")
            else:
                self.logger.debug(f"无适用处理器，跳过文件: {file_event.file_path.name}")

        except Exception as e:
            self.logger.error(f"处理文件事件失败: {e}")

    def _wait_for_file_stable(self, file_path: Path, max_wait: int = 5) -> bool:
        """等待文件写入完成"""
        try:
            if not file_path.exists():
                return False

            last_size = -1
            for _ in range(max_wait):
                current_size = file_path.stat().st_size
                if current_size == last_size and current_size > 0:
                    return True
                last_size = current_size
                time.sleep(0.5)

            return current_size > 0
        except:
            return False


class PipelineWorker:
    """管道工作线程"""

    def __init__(self, task_queue: queue.Queue, processor_registry: ProcessorRegistry,
                 event_manager: PipelineEventManager, completion_callback: Callable):
        self.task_queue = task_queue
        self.processor_registry = processor_registry
        self.event_manager = event_manager
        self.completion_callback = completion_callback
        self.running = True
        self.logger = logging.getLogger("pipeline_worker")

    def run(self):
        """工作线程主循环"""
        while self.running:
            try:
                # 获取任务
                file_event = self.task_queue.get(timeout=1)

                # 记录开始处理事件
                self.event_manager.log_event(file_event, metadata=file_event.metadata)

                # 获取适用的处理器
                applicable_processors = self.processor_registry.get_applicable_processors(file_event)

                if not applicable_processors:
                    self.logger.debug(f"无适用处理器: {file_event.file_path.name}")
                    self.task_queue.task_done()
                    continue

                # 依次执行所有适用的处理器
                for processor in applicable_processors:
                    try:
                        self.logger.info(f"开始处理 {file_event.file_path.name} (处理器: {processor.name})")

                        # 执行处理
                        result, output_files, metadata = processor.process(file_event)

                        # 更新处理器统计
                        processor.update_statistics(result)

                        # 记录处理结果
                        self.event_manager.log_event(
                            file_event, processor.name, result, output_files, metadata
                        )

                        # 调用完成回调
                        if self.completion_callback:
                            self.completion_callback(file_event, processor, result, output_files or [], metadata)

                        self.logger.info(f"处理完成: {processor.name} -> {result.value}")

                    except Exception as e:
                        self.logger.error(f"处理器 {processor.name} 执行失败: {e}")
                        processor.update_statistics(ProcessResult.FAILED)
                        self.event_manager.log_event(
                            file_event, processor.name, ProcessResult.FAILED,
                            metadata={"error": str(e)}
                        )

                self.task_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"工作线程异常: {e}")

    def stop(self):
        """停止工作线程"""
        self.running = False


def main():
    """主函数示例"""
    # 配置
    config = {
        'worker_count': 3,
        'queue_size': 100
    }

    # 创建管道系统
    pipeline = FilePipelineSystem(
        watch_paths=["./input", "./upload"],  # 监控多个目录
        config=config
    )

    # 注册处理器

    # 1. 语音转文字处理器
    audio_processor = AudioToTextProcessor({
        'output_dir': './output/transcripts',
        'language': 'zh-CN',
        'model': 'whisper-large'
    })
    pipeline.register_processor(audio_processor)

    # 2. 知识库加工处理器
    knowledge_processor = KnowledgeProcessor({
        'output_dir': './output/knowledge',
        'enable_summary': True,
        'enable_keywords': True,
        'enable_entities': True,
        'max_keywords': 20
    })
    pipeline.register_processor(knowledge_processor)

    try:
        # 启动管道系统
        pipeline.start()

        # 打印启动信息
        logger.info("=" * 60)
        logger.info("文件处理管道系统已启动")
        logger.info("=" * 60)

        # 显示系统状态
        status = pipeline.get_system_status()
        logger.info(f"监控目录: {', '.join(status['watch_paths'])}")
        logger.info(f"工作线程数: {status['worker_count']}")
        logger.info(f"已注册处理器: {', '.join(status['registered_processors'])}")

        # 创建输入目录（如果不存在）
        for watch_path in pipeline.watch_paths:
            watch_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"监控目录已准备: {watch_path}")

        logger.info("=" * 60)
        logger.info("系统运行中... 请将文件放入监控目录")
        logger.info("支持的音频格式: .wav, .mp3, .m4a, .flac, .aac")
        logger.info("支持的文本格式: .txt, .md")
        logger.info("按 Ctrl+C 停止系统")
        logger.info("=" * 60)

        # 定期显示系统状态
        status_interval = 30  # 每30秒显示一次状态
        last_status_time = time.time()

        while True:
            time.sleep(1)

            # 定期显示状态信息
            current_time = time.time()
            if current_time - last_status_time >= status_interval:
                status = pipeline.get_system_status()
                stats = status['processor_statistics']

                logger.info("=" * 40)
                logger.info("系统状态报告:")
                logger.info(f"队列中任务数: {status['queue_size']}")

                for processor_name, processor_stats in stats.items():
                    logger.info(f"处理器 [{processor_name}]:")
                    logger.info(f"  已处理: {processor_stats['processed']} 个文件")
                    logger.info(f"  成功: {processor_stats['success']} | "
                                f"失败: {processor_stats['failed']} | "
                                f"跳过: {processor_stats['skipped']}")

                logger.info("=" * 40)
                last_status_time = current_time

    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在关闭系统...")

    except Exception as e:
        logger.error(f"系统运行异常: {e}")

    finally:
        # 停止管道系统
        pipeline.stop()

        # 显示最终统计
        final_status = pipeline.get_system_status()
        final_stats = final_status['processor_statistics']

        logger.info("=" * 60)
        logger.info("系统已关闭 - 最终统计报告:")
        logger.info("=" * 60)

        total_processed = 0
        total_success = 0
        total_failed = 0

        for processor_name, stats in final_stats.items():
            logger.info(f"处理器 [{processor_name}]:")
            logger.info(f"  总处理数: {stats['processed']}")
            logger.info(f"  成功: {stats['success']}")
            logger.info(f"  失败: {stats['failed']}")
            logger.info(f"  跳过: {stats['skipped']}")
            logger.info(f"  成功率: {stats['success'] / max(stats['processed'], 1) * 100:.1f}%")
            logger.info("-" * 30)

            total_processed += stats['processed']
            total_success += stats['success']
            total_failed += stats['failed']

        logger.info(f"系统总计:")
        logger.info(f"  总处理数: {total_processed}")
        logger.info(f"  总成功数: {total_success}")
        logger.info(f"  总失败数: {total_failed}")
        logger.info(f"  整体成功率: {total_success / max(total_processed, 1) * 100:.1f}%")
        logger.info("=" * 60)
        logger.info("感谢使用文件处理管道系统!")


def create_sample_files():
    """创建示例文件用于测试"""
    import os

    # 确保输入目录存在
    input_dir = Path("./input")
    input_dir.mkdir(exist_ok=True)

    # 创建示例文本文件
    sample_text = """这是一个示例文本文件，用于测试知识库加工处理器。

内容包括：
1. 产品介绍：我们的智能客服系统能够自动处理用户咨询
2. 技术特点：使用了先进的自然语言处理技术
3. 应用场景：适用于电商、金融、教育等多个行业

联系方式：
电话：400-123-4567
邮箱：support@example.com

本文档最后更新时间：2024年12月"""

    sample_file = input_dir / "sample_text.txt"
    with open(sample_file, 'w', encoding='utf-8') as f:
        f.write(sample_text)

    logger.info(f"已创建示例文件: {sample_file}")

    # 创建示例 Markdown 文件
    sample_md = """# 产品使用手册

## 功能概述
本系统提供完整的文件处理解决方案。

## 主要特性
- **语音转文字**: 支持多种音频格式
- **知识加工**: 自动提取关键信息
- **实时监控**: 自动处理新增文件

## 使用流程
1. 将文件放入监控目录
2. 系统自动识别并处理
3. 查看输出结果

> 注意：请确保文件格式正确
"""

    sample_md_file = input_dir / "manual.md"
    with open(sample_md_file, 'w', encoding='utf-8') as f:
        f.write(sample_md)

    logger.info(f"已创建示例 Markdown 文件: {sample_md_file}")


if __name__ == "__main__":
    # 设置控制台日志格式
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # 获取根日志记录器并配置
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

    # 显示启动横幅
    print("=" * 80)
    print("          文件处理管道系统 v1.0")
    print("        模块化 • 可扩展 • 高效能")
    print("=" * 80)
    print()

    # 询问是否创建示例文件
    try:
        create_samples = input("是否创建示例文件用于测试? (y/N): ").lower().strip()
        if create_samples in ['y', 'yes']:
            create_sample_files()
            print()
    except (EOFError, KeyboardInterrupt):
        print("\n跳过示例文件创建")

    # 启动主程序
    main()