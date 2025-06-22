import json
from enum import Enum
from typing import Dict
from typing import Optional

from pydantic import BaseModel, field_validator
from pydantic import Field
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, func

from dbgpt_app.expend.dao.data_manager import ExpendModel


class SourceType(str, Enum):
    LOCAL = "local"
    FTP = "ftp"


class FileTypeModel(BaseModel):
    extension: str = Field(..., description="文件扩展名，如 .xlsx")
    description: str = Field("", description="文件类型描述")
    enabled: bool = Field(True, description="是否启用")


class LocalDirectoryConfig(BaseModel):
    name: str = Field(..., description="配置名称")
    path: str = Field(..., description="本地目录路径")
    enabled: bool = Field(True, description="是否启用")


class FTPServerConfig(BaseModel):
    name: str = Field(..., description="配置名称")
    host: str = Field(..., description="FTP服务器地址")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    port: int = Field(21, description="端口号")
    remote_dir: str = Field("/", description="远程目录")
    enabled: bool = Field(True, description="是否启用")

class ScanConfigResponse(BaseModel):
    id: int
    name: str
    type: str
    config: Dict
    enabled: bool
    created_at: str
    updated_at: str

    @field_validator('config', mode='before')
    @classmethod
    def parse_config(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v

class GlobalSettingModel(BaseModel):
    target_dir: str = Field(..., description="目标目录路径")


class ScanConfigUpdate(BaseModel):
    enabled: bool = Field(..., description="是否启用")


class ScanResult(BaseModel):
    total_new_files: int
    success_count: int
    failed_count: int
    scan_duration: float
    message: str


class StatisticsResponse(BaseModel):
    total_processed_files: int
    by_source_type: Dict[str, int]
    active_scan_configs: int
    active_file_types: int


class ScanConfigRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    config: Optional[str] = None
    enabled: Optional[bool] = None




class FileTypeRequest(BaseModel):
    extension: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class FileTypeResponse(BaseModel):
    id: Optional[int] = None
    extension: str
    description: Optional[str] = None
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProcessedFileRequest(BaseModel):
    file_id: Optional[str] = None
    source_type: Optional[str] = None
    source_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    target_path: Optional[str] = None


class ProcessedFileResponse(BaseModel):
    id: Optional[int] = None
    file_id: str
    source_type: str
    source_path: str
    file_name: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    target_path: str
    processed_at: Optional[str] = None


class GlobalSettingRequest(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None


class GlobalSettingResponse(BaseModel):
    key: str
    value: str
    updated_at: Optional[str] = None


# SQLAlchemy entities
class ScanConfigEntity(ExpendModel):
    __tablename__ = "scan_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    type = Column(String(50), nullable=False)
    config = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def __repr__(self):
        return (
            f"ScanConfigEntity(id={self.id}, name='{self.name}', "
            f"type='{self.type}', enabled={self.enabled})"
        )


class FileTypeEntity(ExpendModel):
    __tablename__ = "file_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    extension = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def __repr__(self):
        return (
            f"FileTypeEntity(id={self.id}, extension='{self.extension}', "
            f"enabled={self.enabled})"
        )


class ProcessedFileEntity(ExpendModel):
    __tablename__ = "processed_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(500), unique=True, nullable=False)
    source_type = Column(String(50), nullable=False)
    source_path = Column(Text, nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_hash = Column(String(100))
    target_path = Column(Text, nullable=False)
    processed_at = Column(DateTime, default=func.current_timestamp())

    def __repr__(self):
        return (
            f"ProcessedFileEntity(id={self.id}, file_id='{self.file_id}', "
            f"source_type='{self.source_type}', file_name='{self.file_name}')"
        )


class GlobalSettingEntity(ExpendModel):
    __tablename__ = "global_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def __repr__(self):
        return f"GlobalSettingEntity(key='{self.key}', value='{self.value}')"
