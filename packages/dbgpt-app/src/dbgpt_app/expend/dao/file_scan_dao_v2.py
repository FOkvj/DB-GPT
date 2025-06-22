from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, func
from dbgpt.storage.metadata import Model
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel
from dbgpt_app.expend.dao.data_manager import ExpendBaseDao
from dbgpt_app.expend.model.file_scan import ScanConfigEntity, ScanConfigRequest, ScanConfigResponse, \
    FileTypeEntity, FileTypeRequest, FileTypeResponse, ProcessedFileEntity, ProcessedFileRequest, ProcessedFileResponse, \
    GlobalSettingEntity, GlobalSettingRequest, GlobalSettingResponse


# DAO classes
class ScanConfigDao(ExpendBaseDao[ScanConfigEntity, ScanConfigRequest, ScanConfigResponse]):

    def from_request(self, request: Union[ScanConfigRequest, Dict[str, Any]]) -> ScanConfigEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, ScanConfigRequest) else request
        )
        return ScanConfigEntity(**request_dict)

    def to_request(self, entity: ScanConfigEntity) -> ScanConfigRequest:
        """Convert an entity to a request"""
        return ScanConfigRequest(
            name=entity.name,
            type=entity.type,
            config=entity.config,
            enabled=entity.enabled,
        )

    def to_response(self, entity: ScanConfigEntity) -> ScanConfigResponse:
        """Convert an entity to a response"""
        created_at_str = entity.created_at.strftime("%Y-%m-%d %H:%M:%S") if entity.created_at else None
        updated_at_str = entity.updated_at.strftime("%Y-%m-%d %H:%M:%S") if entity.updated_at else None

        return ScanConfigResponse(
            id=entity.id,
            name=entity.name,
            type=entity.type,
            config=entity.config,
            enabled=entity.enabled,
            created_at=created_at_str,
            updated_at=updated_at_str,
        )

    def from_response(self, response: Union[ScanConfigResponse, Dict[str, Any]]) -> ScanConfigEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, ScanConfigResponse) else response
        )
        return ScanConfigEntity(**response_dict)

    def get_config_by_name(self, name: str) -> Optional[ScanConfigResponse]:
        """Get scan config by name"""
        return self.get_one({"name": name})

    def get_enabled_configs(self) -> List[ScanConfigResponse]:
        """Get all enabled scan configs"""
        return self.get_list({"enabled": True})

    def upsert_config(self, name: str, type: str, config: str, enabled: bool = True) -> ScanConfigResponse:
        """Insert or update scan config"""
        existing = self.get_config_by_name(name)

        if existing:
            # Update existing config
            update_request = ScanConfigRequest(
                type=type,
                config=config,
                enabled=enabled,
            )
            return self.update({"name": name}, update_request)
        else:
            # Create new config
            create_request = ScanConfigRequest(
                name=name,
                type=type,
                config=config,
                enabled=enabled,
            )
            return self.create(create_request)

    def update_config_status(self, name: str, enabled: bool) -> Optional[ScanConfigResponse]:
        """Update scan config enabled status"""
        try:
            update_request = ScanConfigRequest(enabled=enabled)
            return self.update({"name": name}, update_request)
        except Exception:
            return None

    def remove_config(self, name: str) -> bool:
        """Remove scan config by name"""
        try:
            self.delete({"name": name})
            return True
        except Exception:
            return False


class FileTypeDao(ExpendBaseDao[FileTypeEntity, FileTypeRequest, FileTypeResponse]):

    def from_request(self, request: Union[FileTypeRequest, Dict[str, Any]]) -> FileTypeEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, FileTypeRequest) else request
        )
        return FileTypeEntity(**request_dict)

    def to_request(self, entity: FileTypeEntity) -> FileTypeRequest:
        """Convert an entity to a request"""
        return FileTypeRequest(
            extension=entity.extension,
            description=entity.description,
            enabled=entity.enabled,
        )

    def to_response(self, entity: FileTypeEntity) -> FileTypeResponse:
        """Convert an entity to a response"""
        created_at_str = entity.created_at.strftime("%Y-%m-%d %H:%M:%S") if entity.created_at else None
        updated_at_str = entity.updated_at.strftime("%Y-%m-%d %H:%M:%S") if entity.updated_at else None

        return FileTypeResponse(
            id=entity.id,
            extension=entity.extension,
            description=entity.description,
            enabled=entity.enabled,
            created_at=created_at_str,
            updated_at=updated_at_str,
        )

    def from_response(self, response: Union[FileTypeResponse, Dict[str, Any]]) -> FileTypeEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, FileTypeResponse) else response
        )
        return FileTypeEntity(**response_dict)

    def get_file_type_by_extension(self, extension: str) -> Optional[FileTypeResponse]:
        """Get file type by extension"""
        return self.get_one({"extension": extension.lower()})

    def get_enabled_file_types(self) -> List[FileTypeResponse]:
        """Get all enabled file types"""
        return self.get_list({"enabled": True})

    def add_file_type(self, extension: str, description: str = "", enabled: bool = True) -> Optional[FileTypeResponse]:
        """Add new file type"""
        try:
            create_request = FileTypeRequest(
                extension=extension.lower(),
                description=description,
                enabled=enabled,
            )
            return self.create(create_request)
        except Exception:
            return None

    def update_file_type(self, extension: str, description: str = None, enabled: bool = None) -> Optional[
        FileTypeResponse]:
        """Update file type"""
        try:
            update_request = FileTypeRequest()
            if description is not None:
                update_request.description = description
            if enabled is not None:
                update_request.enabled = enabled

            return self.update({"extension": extension.lower()}, update_request)
        except Exception:
            return None

    def remove_file_type(self, extension: str) -> bool:
        """Remove file type by extension"""
        try:
            self.delete({"extension": extension.lower()})
            return True
        except Exception:
            return False


class ProcessedFileDao(ExpendBaseDao[ProcessedFileEntity, ProcessedFileRequest, ProcessedFileResponse]):

    def from_request(self, request: Union[ProcessedFileRequest, Dict[str, Any]]) -> ProcessedFileEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, ProcessedFileRequest) else request
        )
        return ProcessedFileEntity(**request_dict)

    def to_request(self, entity: ProcessedFileEntity) -> ProcessedFileRequest:
        """Convert an entity to a request"""
        return ProcessedFileRequest(
            file_id=entity.file_id,
            source_type=entity.source_type,
            source_path=entity.source_path,
            file_name=entity.file_name,
            file_size=entity.file_size,
            file_hash=entity.file_hash,
            target_path=entity.target_path,
        )

    def to_response(self, entity: ProcessedFileEntity) -> ProcessedFileResponse:
        """Convert an entity to a response"""
        processed_at_str = entity.processed_at.strftime("%Y-%m-%d %H:%M:%S") if entity.processed_at else None

        return ProcessedFileResponse(
            id=entity.id,
            file_id=entity.file_id,
            source_type=entity.source_type,
            source_path=entity.source_path,
            file_name=entity.file_name,
            file_size=entity.file_size,
            file_hash=entity.file_hash,
            target_path=entity.target_path,
            processed_at=processed_at_str,
        )

    def from_response(self, response: Union[ProcessedFileResponse, Dict[str, Any]]) -> ProcessedFileEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, ProcessedFileResponse) else response
        )
        return ProcessedFileEntity(**response_dict)

    def is_file_processed(self, file_id: str) -> bool:
        """Check if file is already processed"""
        result = self.get_one({"file_id": file_id})
        return result is not None

    def mark_file_processed(self, file_id: str, source_type: str, source_path: str,
                            file_name: str, file_size: int, file_hash: str, target_path: str) -> Optional[
        ProcessedFileResponse]:
        """Mark file as processed"""
        try:
            request = ProcessedFileRequest(
                file_id=file_id,
                source_type=source_type,
                source_path=source_path,
                file_name=file_name,
                file_size=file_size,
                file_hash=file_hash,
                target_path=target_path,
            )
            return self.create(request)
        except Exception:
            return None

    def get_processed_files_by_source_type(self, source_type: str) -> List[ProcessedFileResponse]:
        """Get processed files by source type"""
        return self.get_list({"source_type": source_type})

    def clear_all_processed_files(self) -> bool:
        """Clear all processed file records"""
        try:
            with self.session() as session:
                session.query(ProcessedFileEntity).delete()
                session.commit()
            return True
        except Exception:
            return False


class GlobalSettingDao(ExpendBaseDao[GlobalSettingEntity, GlobalSettingRequest, GlobalSettingResponse]):

    def from_request(self, request: Union[GlobalSettingRequest, Dict[str, Any]]) -> GlobalSettingEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, GlobalSettingRequest) else request
        )
        return GlobalSettingEntity(**request_dict)

    def to_request(self, entity: GlobalSettingEntity) -> GlobalSettingRequest:
        """Convert an entity to a request"""
        return GlobalSettingRequest(
            key=entity.key,
            value=entity.value,
        )

    def to_response(self, entity: GlobalSettingEntity) -> GlobalSettingResponse:
        """Convert an entity to a response"""
        updated_at_str = entity.updated_at.strftime("%Y-%m-%d %H:%M:%S") if entity.updated_at else None

        return GlobalSettingResponse(
            key=entity.key,
            value=entity.value,
            updated_at=updated_at_str,
        )

    def from_response(self, response: Union[GlobalSettingResponse, Dict[str, Any]]) -> GlobalSettingEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, GlobalSettingResponse) else response
        )
        return GlobalSettingEntity(**response_dict)

    def get_setting(self, key: str) -> Optional[GlobalSettingResponse]:
        """Get global setting by key"""
        return self.get_one({"key": key})

    def set_setting(self, key: str, value: str) -> GlobalSettingResponse:
        """Set global setting"""
        existing = self.get_setting(key)

        if existing:
            # Update existing setting
            update_request = GlobalSettingRequest(value=value)
            return self.update({"key": key}, update_request)
        else:
            # Create new setting
            create_request = GlobalSettingRequest(key=key, value=value)
            return self.create(create_request)

    def get_all_settings(self) -> List[GlobalSettingResponse]:
        """Get all global settings"""
        return self.get_list({})