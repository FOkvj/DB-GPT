"""
Pipeline Event DAO 层实现
将PipelineEventManager重构为DAO模式，参照SchedulerManager的设计
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text, func

from dbgpt_app.expend.dao.data_manager import ExpendBaseDao, ExpendModel


# Pydantic schemas for request/response
class PipelineEventRequest(BaseModel):
    file_path: str
    event_type: str
    processor_name: Optional[str] = None
    result: Optional[str] = None
    event_metadata: Optional[Dict] = None
    output_files: Optional[List[str]] = None
    file_hash: Optional[str] = None


class PipelineEventResponse(BaseModel):
    id: Optional[int] = None
    file_path: str
    event_type: str
    processor_name: Optional[str] = None
    result: Optional[str] = None
    event_metadata: Optional[Dict] = None
    output_files: Optional[List[str]] = None
    file_hash: Optional[str] = None
    created_time: Optional[str] = None


class FileProcessingStatusRequest(BaseModel):
    file_path: str
    processor_name: str
    file_hash: str


class FileProcessingStatusResponse(BaseModel):
    file_path: str
    processor_name: str
    file_hash: str
    is_processed: bool
    last_processed_time: Optional[str] = None


# SQLAlchemy entities
class PipelineEventEntity(ExpendModel):
    __tablename__ = "pipeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False)
    processor_name = Column(String(100))
    result = Column(String(20))
    event_metadata = Column(Text)  # JSON string - renamed to avoid SQLAlchemy reserved word
    output_files = Column(Text)  # JSON string
    file_hash = Column(String(32))
    created_time = Column(DateTime, default=func.current_timestamp())

    def __repr__(self):
        return (
            f"PipelineEventEntity(id={self.id}, file_path='{self.file_path}', "
            f"event_type='{self.event_type}', processor='{self.processor_name}', "
            f"result='{self.result}')"
        )


# DAO classes
class PipelineEventDao(ExpendBaseDao[PipelineEventEntity, PipelineEventRequest, PipelineEventResponse]):

    def from_request(self, request: Union[PipelineEventRequest, Dict[str, Any]]) -> PipelineEventEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, PipelineEventRequest) else request
        )

        # 处理JSON字段
        event_metadata_json = json.dumps(request_dict.get('event_metadata') or {})
        output_files_json = json.dumps(request_dict.get('output_files') or [])

        return PipelineEventEntity(
            file_path=request_dict['file_path'],
            event_type=request_dict['event_type'],
            processor_name=request_dict.get('processor_name'),
            result=request_dict.get('result'),
            event_metadata=event_metadata_json,
            output_files=output_files_json,
            file_hash=request_dict.get('file_hash')
        )

    def to_request(self, entity: PipelineEventEntity) -> PipelineEventRequest:
        """Convert an entity to a request"""
        try:
            event_metadata = json.loads(entity.event_metadata) if entity.event_metadata else {}
        except:
            event_metadata = {}

        try:
            output_files = json.loads(entity.output_files) if entity.output_files else []
        except:
            output_files = []

        return PipelineEventRequest(
            file_path=entity.file_path,
            event_type=entity.event_type,
            processor_name=entity.processor_name,
            result=entity.result,
            event_metadata=event_metadata,
            output_files=output_files,
            file_hash=entity.file_hash
        )

    def to_response(self, entity: PipelineEventEntity) -> PipelineEventResponse:
        """Convert an entity to a response"""
        try:
            event_metadata = json.loads(entity.event_metadata) if entity.event_metadata else {}
        except:
            event_metadata = {}

        try:
            output_files = json.loads(entity.output_files) if entity.output_files else []
        except:
            output_files = []

        created_time_str = entity.created_time.strftime("%Y-%m-%d %H:%M:%S") if entity.created_time else None

        return PipelineEventResponse(
            id=entity.id,
            file_path=entity.file_path,
            event_type=entity.event_type,
            processor_name=entity.processor_name,
            result=entity.result,
            event_metadata=event_metadata,
            output_files=output_files,
            file_hash=entity.file_hash,
            created_time=created_time_str
        )

    def from_response(self, response: Union[PipelineEventResponse, Dict[str, Any]]) -> PipelineEventEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, PipelineEventResponse) else response
        )

        # 处理JSON字段
        event_metadata_json = json.dumps(response_dict.get('event_metadata') or {})
        output_files_json = json.dumps(response_dict.get('output_files') or [])

        return PipelineEventEntity(
            id=response_dict.get('id'),
            file_path=response_dict['file_path'],
            event_type=response_dict['event_type'],
            processor_name=response_dict.get('processor_name'),
            result=response_dict.get('result'),
            event_metadata=event_metadata_json,
            output_files=output_files_json,
            file_hash=response_dict.get('file_hash')
        )

    def log_event(self, file_path: str, event_type: str, processor_name: str = None,
                  result: str = None, output_files: List[str] = None,
                  event_metadata: Dict = None, file_hash: str = None) -> Optional[PipelineEventResponse]:
        """记录管道事件"""
        try:
            request = PipelineEventRequest(
                file_path=str(Path(file_path).absolute()),
                event_type=event_type,
                processor_name=processor_name,
                result=result,
                event_metadata=event_metadata or {},
                output_files=output_files or [],
                file_hash=file_hash
            )
            return self.create(request)
        except Exception as e:
            print(f"记录事件失败: {e}")
            return None

    def get_file_processing_history(self, file_path: str) -> List[PipelineEventResponse]:
        """获取文件的处理历史"""
        try:
            absolute_path = str(Path(file_path).absolute())
            # 使用 get_list_page 按时间倒序获取
            result = self.get_list_page(
                {"file_path": absolute_path},
                page=1,
                page_size=1000,  # 足够大的数量
                asc_order_column="created_time"
            )
            return result.items
        except Exception as e:
            print(f"获取处理历史失败: {e}")
            return []

    def is_file_processed_successfully(self, file_path: str, processor_name: str, file_hash: str) -> bool:
        """检查文件是否已被特定处理器成功处理过"""
        try:
            absolute_path = str(Path(file_path).absolute())

            # 查询条件
            conditions = {
                "file_path": absolute_path,
                "processor_name": processor_name,
                "result": "success",
                "file_hash": file_hash
            }

            # 查询是否存在符合条件的记录
            result = self.get_list_page(conditions, page=1, page_size=1)
            return len(result.items) > 0

        except Exception as e:
            print(f"检查处理状态失败: {e}")
            return False

    def get_unprocessed_files(self, watch_paths: List[Path], processors: Dict[str, Any]) -> List[Dict]:
        """获取未处理的文件列表"""
        unprocessed_files = []

        for watch_path in watch_paths:
            if not watch_path.exists():
                continue

            # 递归扫描目录中的所有文件
            for file_path in watch_path.rglob('*'):
                if not file_path.is_file():
                    continue

                try:
                    # 计算文件哈希
                    file_hash = self._calculate_file_hash(file_path)

                    # 检查是否有处理器可以处理此文件
                    applicable_processors = []
                    for processor in processors.values():
                        # 这里需要根据实际的处理器接口来判断
                        if hasattr(processor, 'can_process'):
                            # 创建临时的文件事件对象进行判断
                            file_event = {
                                'file_path': file_path,
                                'file_hash': file_hash
                            }

                            if processor.can_process(file_event):
                                # 检查是否已被成功处理过
                                if not self.is_file_processed_successfully(
                                        str(file_path), processor.name, file_hash):
                                    applicable_processors.append(processor)

                    # 如果有未处理的处理器，则加入队列
                    if applicable_processors:
                        unprocessed_files.append({
                            'file_path': str(file_path),
                            'file_hash': file_hash,
                            'event_type': 'startup_scan',
                            'applicable_processors': [p.name for p in applicable_processors]
                        })

                except Exception as e:
                    print(f"检查文件 {file_path} 时出错: {e}")

        return unprocessed_files

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        try:
            import hashlib
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
        except:
            pass
        return ""

    def get_processor_statistics(self, processor_name: str = None) -> Dict:
        """获取处理器统计信息"""
        try:
            conditions = {}
            if processor_name:
                conditions["processor_name"] = processor_name

            # 获取所有相关记录
            all_records = self.get_list(conditions)

            stats = {
                'total': len(all_records),
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'partial': 0
            }

            for record in all_records:
                result = record.result
                if result == 'success':
                    stats['success'] += 1
                elif result == 'failed':
                    stats['failed'] += 1
                elif result == 'skipped':
                    stats['skipped'] += 1
                elif result == 'partial':
                    stats['partial'] += 1

            return stats

        except Exception as e:
            print(f"获取处理器统计失败: {e}")
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'partial': 0}

    def get_recent_events(self, limit: int = 50) -> List[PipelineEventResponse]:
        """获取最近的事件"""
        try:
            result = self.get_list_page(
                {},
                page=1,
                page_size=limit,
                desc_order_column="created_time"
            )
            return result.items
        except Exception as e:
            print(f"获取最近事件失败: {e}")
            return []

    def clean_old_events(self, days: int = 30) -> bool:
        """清理旧事件记录"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)

            # 注意：这里需要根据实际的DAO实现来进行批量删除
            # 由于BaseDao没有直接的批量删除方法，这里留作扩展点
            print(f"清理 {days} 天前的事件记录功能需要根据具体需求实现")
            return True
        except Exception as e:
            print(f"清理旧事件记录失败: {e}")
            return False

    def get_file_processing_summary(self, file_path: str) -> Dict:
        """获取文件处理摘要"""
        try:
            absolute_path = str(Path(file_path).absolute())
            history = self.get_file_processing_history(absolute_path)

            if not history:
                return {
                    'status': 'pending',
                    'processors': [],
                    'last_processed': None,
                    'error_message': None
                }

            processors = []
            last_processed = None
            error_msg = None
            has_success = False
            has_failure = False

            for event in history:
                if event.processor_name and event.processor_name not in processors:
                    processors.append(event.processor_name)

                if event.result == 'success':
                    has_success = True
                    last_processed = event.created_time
                elif event.result == 'failed':
                    has_failure = True
                    if event.event_metadata and 'error' in event.event_metadata:
                        error_msg = event.event_metadata['error']

            # 确定状态
            if has_success and not has_failure:
                status = 'completed'
            elif has_failure:
                status = 'failed'
            elif processors:
                status = 'processing'
            else:
                status = 'pending'

            return {
                'status': status,
                'processors': processors,
                'last_processed': last_processed,
                'error_message': error_msg
            }

        except Exception as e:
            print(f"获取文件处理摘要失败: {e}")
            return {
                'status': 'unknown',
                'processors': [],
                'last_processed': None,
                'error_message': str(e)
            }


# 使用示例和测试函数
def test_pipeline_event_dao():
    """测试 Pipeline Event DAO"""
    print("=== 测试 Pipeline Event DAO ===")

    # 确保数据库已初始化
    from dbgpt.storage.metadata import db
    if not db.is_initialized:
        db.init_default_db("pipeline_test.db")
        db.create_all()

    # 创建DAO实例
    event_dao = PipelineEventDao()

    # 测试记录事件
    print("\n1. 测试记录事件")
    test_file_path = "/test/path/audio.wav"
    test_file_hash = "test_hash_123"

    # 记录文件创建事件
    response1 = event_dao.log_event(
        file_path=test_file_path,
        event_type="created",
        file_hash=test_file_hash
    )
    print(f"记录创建事件: {response1.id if response1 else 'Failed'}")

    # 记录处理事件
    response2 = event_dao.log_event(
        file_path=test_file_path,
        event_type="processed",
        processor_name="audio_to_text",
        result="success",
        metadata={"processing_time": 5.2, "transcript_length": 1000},
        output_files=["/output/audio_transcript.txt"],
        file_hash=test_file_hash
    )
    print(f"记录处理事件: {response2.id if response2 else 'Failed'}")

    # 测试获取处理历史
    print("\n2. 测试获取处理历史")
    history = event_dao.get_file_processing_history(test_file_path)
    print(f"获取到 {len(history)} 条历史记录")
    for event in history:
        print(f"  - {event.event_type}: {event.processor_name} -> {event.result}")

    # 测试检查文件是否已处理
    print("\n3. 测试检查文件处理状态")
    is_processed = event_dao.is_file_processed_successfully(
        test_file_path, "audio_to_text", test_file_hash
    )
    print(f"文件是否已被成功处理: {is_processed}")

    # 测试错误处理事件
    print("\n4. 测试错误处理事件")
    response3 = event_dao.log_event(
        file_path="/test/path/error.wav",
        event_type="processed",
        processor_name="audio_to_text",
        result="failed",
        metadata={"error": "文件格式不支持"},
        file_hash="error_hash_456"
    )
    print(f"记录错误事件: {response3.id if response3 else 'Failed'}")

    # 测试获取处理器统计
    print("\n5. 测试获取处理器统计")
    stats = event_dao.get_processor_statistics("audio_to_text")
    print(f"audio_to_text 处理器统计: {stats}")

    # 测试获取文件处理摘要
    print("\n6. 测试获取文件处理摘要")
    summary = event_dao.get_file_processing_summary(test_file_path)
    print(f"文件处理摘要: {summary}")

    # 测试获取最近事件
    print("\n7. 测试获取最近事件")
    recent_events = event_dao.get_recent_events(limit=5)
    print(f"最近 {len(recent_events)} 个事件:")
    for event in recent_events:
        print(f"  - {event.created_time}: {event.file_path} ({event.event_type})")

    print("\n=== Pipeline Event DAO 测试完成 ===")


if __name__ == "__main__":
    test_pipeline_event_dao()