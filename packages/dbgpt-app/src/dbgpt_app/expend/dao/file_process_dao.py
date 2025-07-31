from typing import Any, Dict, List, Optional, Union, Generic, TypeVar
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func

from dbgpt.util import PaginationResult
from dbgpt_app.expend.dao.data_manager import ExpendBaseDao, ExpendModel

T = TypeVar('T')




# 枚举定义
class SourceType(str, Enum):
    """源类型枚举"""
    FTP = "ftp"
    STT = "stt"


class ProcessStatus(str, Enum):
    """处理状态枚举"""
    FAILED = "failed"
    SUCCESS = "success"
    RETRYING = "retrying"
    WAIT = "wait" # 等待处理
    PROCESSING = "processing" # 处理中，如果source_type是ftp表示文件下载中
    DOWNLOADING = "downloading"



# 实体类定义
class FileProcessingEntity(ExpendModel):
    """文件处理实体类"""
    __tablename__ = "file_processing"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    file_id = Column(String(255), unique=True, nullable=False, comment="文件唯一ID") # 用于文件的
    file_name = Column(String(500), nullable=False, comment="文件名")
    source_type = Column(String(50), nullable=False, comment="源类型")
    source_id = Column(String(255), nullable=False, comment="源ID，用于获取knowledge_mapping")
    source_file_id = Column(String(255), nullable=True, comment="源文件ID") # 用于查询文件是否被扫描过
    file_type = Column(String(50), nullable=True, comment="文件类型")
    size = Column(Integer, nullable=True, comment="文件大小")
    status = Column(String(50), nullable=False, default=ProcessStatus.WAIT, comment="处理状态")
    start_time = Column(DateTime, nullable=True, comment="开始处理时间")
    end_time = Column(DateTime, nullable=True, comment="处理结束时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


# 请求模型
class FileProcessingRequest(BaseModel):
    """文件处理请求模型"""
    file_id: Optional[str] = None
    source_file_id: Optional[str] = None # 扫描文件的id
    file_name: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    file_type: Optional[str] = None
    size: Optional[int] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


# 响应模型
class FileProcessingResponse(BaseModel):
    """文件处理响应模型"""
    id: int
    file_id: str
    file_name: str
    source_type: str
    source_file_id: Optional[str] = None # 扫描文件的id
    source_id: str
    file_type: Optional[str] = None
    size: Optional[int] = None
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# 分页查询请求模型
class FileProcessingPageRequest(BaseModel):
    """文件处理分页查询请求模型"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页大小")
    file_id: Optional[str] = None
    source_file_id: Optional[str] = None # 扫描文件的id
    file_name: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    file_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None  # 开始日期过滤
    end_date: Optional[str] = None  # 结束日期过滤


# DAO 类
class FileProcessingDao(ExpendBaseDao[FileProcessingEntity, FileProcessingRequest, FileProcessingResponse]):
    """文件处理 DAO 类"""

    def from_request(self, request: Union[FileProcessingRequest, Dict[str, Any]]) -> FileProcessingEntity:
        """将请求转换为实体"""
        request_dict = (
            request.dict() if isinstance(request, FileProcessingRequest) else request
        )
        return FileProcessingEntity(**request_dict)

    def to_request(self, entity: FileProcessingEntity) -> FileProcessingRequest:
        """将实体转换为请求"""
        return FileProcessingRequest(
            file_id=entity.file_id,
            file_name=entity.file_name,
            source_type=entity.source_type,
            source_id=entity.source_id,
            source_file_id=entity.source_file_id,
            file_type=entity.file_type,
            size=entity.size,
            status=entity.status,
            start_time=entity.start_time,
            end_time=entity.end_time,
        )

    def to_response(self, entity: FileProcessingEntity) -> FileProcessingResponse:
        """将实体转换为响应"""
        start_time_str = entity.start_time.strftime("%Y-%m-%d %H:%M:%S") if entity.start_time else None
        end_time_str = entity.end_time.strftime("%Y-%m-%d %H:%M:%S") if entity.end_time else None
        created_at_str = entity.created_at.strftime("%Y-%m-%d %H:%M:%S") if entity.created_at else None
        updated_at_str = entity.updated_at.strftime("%Y-%m-%d %H:%M:%S") if entity.updated_at else None

        return FileProcessingResponse(
            id=entity.id,
            file_id=entity.file_id,
            source_file_id=entity.source_file_id,
            file_name=entity.file_name,
            source_type=entity.source_type,
            source_id=entity.source_id,
            file_type=entity.file_type,
            size=entity.size,
            status=entity.status,
            start_time=start_time_str,
            end_time=end_time_str,
            created_at=created_at_str,
            updated_at=updated_at_str,
        )

    def from_response(self, response: Union[FileProcessingResponse, Dict[str, Any]]) -> FileProcessingEntity:
        """将响应转换为实体"""
        response_dict = (
            response.dict() if isinstance(response, FileProcessingResponse) else response
        )
        return FileProcessingEntity(**response_dict)

    # 基础 CRUD 操作
    def create_file_processing(self, file_id: str, file_name: str, source_type: str,
                               source_id: str, file_type: str = None, size: int = None,
                               status: str = ProcessStatus.WAIT) -> Optional[FileProcessingResponse]:
        """创建文件处理记录"""
        try:
            create_request = FileProcessingRequest(
                file_id=file_id,
                file_name=file_name,
                source_type=source_type,
                source_id=source_id,
                file_type=file_type,
                size=size,
                status=status,
            )
            return self.create(create_request)
        except Exception:
            return None

    def get_file_processing_by_id(self, record_id: int) -> Optional[FileProcessingResponse]:
        """根据ID获取文件处理记录"""
        return self.get_one({"id": record_id})

    def get_file_processing_by_file_id(self, file_id: str) -> Optional[FileProcessingResponse]:
        """根据文件ID获取文件处理记录"""
        return self.get_one({"file_id": file_id})

    def update_file_processing(self, record_id: int, **kwargs) -> Optional[FileProcessingResponse]:
        """更新文件处理记录"""
        try:
            update_request = FileProcessingRequest(**kwargs)
            return self.update({"id": record_id}, update_request)
        except Exception:
            return None

    def update_file_processing_by_file_id(self, file_id: str, **kwargs) -> Optional[FileProcessingResponse]:
        """根据文件ID更新文件处理记录"""
        try:
            update_request = FileProcessingRequest(**kwargs)
            return self.update({"file_id": file_id}, update_request)
        except Exception:
            return None

    def delete_file_processing(self, record_id: int) -> bool:
        """删除文件处理记录"""
        try:
            self.delete({"id": record_id})
            return True
        except Exception:
            return False

    def delete_file_processing_by_file_id(self, file_id: str) -> bool:
        """根据文件ID删除文件处理记录"""
        try:
            self.delete({"file_id": file_id})
            return True
        except Exception:
            return False

    # 查询操作
    def get_file_processing_list(self, **filters) -> List[FileProcessingResponse]:
        """获取文件处理记录列表"""
        return self.get_list(filters)

    def get_files_by_source_type(self, source_type: str) -> List[FileProcessingResponse]:
        """根据源类型获取文件列表"""
        return self.get_list({"source_type": source_type})

    def get_files_by_source_id(self, source_id: str) -> List[FileProcessingResponse]:
        """根据源ID获取文件列表"""
        return self.get_list({"source_id": source_id})

    def get_files_by_status(self, status: str) -> List[FileProcessingResponse]:
        """根据状态获取文件列表"""
        return self.get_list({"status": status})

    def get_processing_files(self) -> List[FileProcessingResponse]:
        """获取正在处理的文件列表"""
        return self.get_list({"status": ProcessStatus.PROCESSING})

    def get_failed_files(self) -> List[FileProcessingResponse]:
        """获取处理失败的文件列表"""
        return self.get_list({"status": ProcessStatus.FAILED})

    def get_waiting_files(self) -> List[FileProcessingResponse]:
        """获取等待处理的文件列表"""
        return self.get_list({"status": ProcessStatus.WAIT})

    def get_count(self, query_request: Union[FileProcessingRequest, Dict[str, Any]]) -> int:
        """获取符合条件的记录数量"""
        try:
            with self.session() as session:
                query = self._create_query_object(session, query_request)
                return query.count()
        except Exception:
            return 0

    # 分页查询
    def get_file_processing_page(self, request: FileProcessingPageRequest) -> PaginationResult[
        FileProcessingResponse]:
        """分页查询文件处理记录"""
        query_request = FileProcessingRequest(
            file_id=request.file_id,
            source_file_id=request.source_file_id,
            file_name=request.file_name,
            source_type=request.source_type,
            source_id=request.source_id,
            file_type=request.file_type,
            status=request.status,
            start_time=datetime.strptime(request.start_date, "%Y-%m-%d") if request.start_date else None,
            end_time=datetime.strptime(request.end_date, "%Y-%m-%d") if request.end_date else None
        )

        return self.get_list_page(
            query_request=query_request,
            page=request.page,
            page_size=request.page_size,
            desc_order_column="created_at"
        )

    # 状态更新操作
    def update_status(self, file_id: str, status: str, start_time: datetime = None,
                      end_time: datetime = None) -> Optional[FileProcessingResponse]:
        """更新文件处理状态"""
        update_data = {"status": status}
        if start_time:
            update_data["start_time"] = start_time
        if end_time:
            update_data["end_time"] = end_time

        return self.update_file_processing_by_file_id(file_id, **update_data)





    # 批量操作
    def batch_update_status(self, file_ids: List[str], status: str) -> int:
        """批量更新状态"""
        try:
            with self.session() as session:
                updated_count = session.query(FileProcessingEntity).filter(
                    FileProcessingEntity.file_id.in_(file_ids)
                ).update({"status": status, "updated_at": datetime.now()})
                session.commit()
                return updated_count
        except Exception:
            return 0

    def batch_delete(self, file_ids: List[str]) -> int:
        """批量删除记录"""
        try:
            with self.session() as session:
                deleted_count = session.query(FileProcessingEntity).filter(
                    FileProcessingEntity.file_id.in_(file_ids)
                ).delete()
                session.commit()
                return deleted_count
        except Exception:
            return 0

    # 统计操作
    def get_status_statistics(self) -> Dict[str, int]:
        """获取状态统计"""
        try:
            with self.session() as session:
                stats = {}
                for status in ProcessStatus:
                    count = session.query(FileProcessingEntity).filter(
                        FileProcessingEntity.status == status
                    ).count()
                    stats[status.value] = count
                return stats
        except Exception:
            return {}

    def get_source_type_statistics(self) -> Dict[str, int]:
        """获取源类型统计"""
        try:
            with self.session() as session:
                stats = {}
                for source_type in SourceType:
                    count = session.query(FileProcessingEntity).filter(
                        FileProcessingEntity.source_type == source_type
                    ).count()
                    stats[source_type.value] = count
                return stats
        except Exception:
            return {}

    def clear_all_records(self) -> bool:
        """清空所有记录"""
        try:
            with self.session() as session:
                session.query(FileProcessingEntity).delete()
                session.commit()
            return True
        except Exception:
            return False

    def get_files_by_source_file_id(self, source_file_id:str) -> List[FileProcessingResponse]:
        return self.get_list({"source_file_id": source_file_id})