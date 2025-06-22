from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class FileStatus(Enum):
    """文件状态枚举"""
    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 处理失败
    SKIPPED = "skipped"  # 已跳过


@dataclass
class FileInfo:
    """文件信息数据类"""
    path: str
    name: str
    size: int
    created_time: str
    modified_time: str
    extension: str
    status: FileStatus
    processors: List[str]
    last_processed: Optional[str] = None
    error_message: Optional[str] = None