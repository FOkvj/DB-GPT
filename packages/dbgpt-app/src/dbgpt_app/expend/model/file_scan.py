from enum import Enum
from typing import Dict

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    LOCAL = "local"
    FTP = "ftp"

class FileTypeModel(BaseModel):
    extension: str = Field(..., description="文件扩展名，如 .xlsx")
    description: str = Field("", description="文件类型描述")
    enabled: bool = Field(True, description="是否启用")

class FileTypeResponse(BaseModel):
    id: int
    extension: str
    description: str
    enabled: bool
    created_at: str

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

class ProcessedFileResponse(BaseModel):
    id: int
    file_id: str
    source_type: str
    source_path: str
    file_name: str
    file_size: int
    file_hash: str
    target_path: str
    processed_at: str

class StatisticsResponse(BaseModel):
    total_processed_files: int
    by_source_type: Dict[str, int]
    active_scan_configs: int
    active_file_types: int