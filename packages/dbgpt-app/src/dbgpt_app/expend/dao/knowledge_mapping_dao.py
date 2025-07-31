"""
Knowledge Base Mapping DAO 层实现
"""
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean

from dbgpt_app.expend.dao.data_manager import ExpendBaseDao, ExpendModel


class KnowledgeBaseMappingDaoRequest(BaseModel):
    scan_config_name: str
    knowledge_base_id: str
    knowledge_base_name: str
    enabled: bool

class KnowledgeBaseMappingDaoResponse(BaseModel):
    id: Optional[int] = None
    scan_config_name: str
    knowledge_base_id: str
    knowledge_base_name: str
    enabled: bool

class KnowledgeBaseMappingEntity(ExpendModel):
    __tablename__ = "knowledge_base_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_config_name = Column(String(100), nullable=False, unique=True)
    knowledge_base_id = Column(String(100), nullable=False)
    knowledge_base_name = Column(String(200), nullable=False)
    enabled = Column(Boolean, default=True)

class KnowledgeBaseMappingDao(ExpendBaseDao[KnowledgeBaseMappingEntity, KnowledgeBaseMappingDaoRequest, KnowledgeBaseMappingDaoResponse]):

    def from_request(self, request: Union[KnowledgeBaseMappingDaoRequest, Dict[str, Any]]) -> KnowledgeBaseMappingEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, KnowledgeBaseMappingDaoRequest) else request
        )

        return KnowledgeBaseMappingEntity(
            scan_config_name=request_dict.get('scan_config_name'),
            knowledge_base_id=request_dict.get('knowledge_base_id'),
            knowledge_base_name=request_dict.get('knowledge_base_name'),
            enabled=request_dict.get('enabled', True)
        )

    def to_request(self, entity: KnowledgeBaseMappingEntity) -> KnowledgeBaseMappingDaoRequest:
        """Convert an entity to a request"""
        return KnowledgeBaseMappingDaoRequest(
            scan_config_name=entity.scan_config_name,
            knowledge_base_id=entity.knowledge_base_id,
            knowledge_base_name=entity.knowledge_base_name,
            enabled=entity.enabled
        )

    def to_response(self, entity: KnowledgeBaseMappingEntity) -> KnowledgeBaseMappingDaoResponse:
        """Convert an entity to a response"""
        return KnowledgeBaseMappingDaoResponse(
            id=entity.id,
            scan_config_name=entity.scan_config_name,
            knowledge_base_id=entity.knowledge_base_id,
            knowledge_base_name=entity.knowledge_base_name,
            enabled=entity.enabled
        )

    def from_response(self, response: Union[KnowledgeBaseMappingDaoResponse, Dict[str, Any]]) -> KnowledgeBaseMappingEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, KnowledgeBaseMappingDaoResponse) else response
        )

        return KnowledgeBaseMappingEntity(
            id=response_dict.get('id'),
            scan_config_name=response_dict.get('scan_config_name'),
            knowledge_base_id=response_dict.get('knowledge_base_id'),
            knowledge_base_name=response_dict.get('knowledge_base_name'),
            enabled=response_dict.get('enabled', True)
        )

    def get_all_mappings(self) -> List[Dict]:
        """获取所有映射配置"""
        entities = self.get_list({})
        return [self.to_response(entity).dict() for entity in entities]

    def get_mapping_by_scan_config_name(self, scan_config_name: str) -> Optional[KnowledgeBaseMappingDaoResponse]:
        """根据扫描配置名称获取映射配置"""
        return self.get_one({'scan_config_name': scan_config_name})

    def save_mappings(self, mappings: List[KnowledgeBaseMappingDaoRequest]):
        """保存映射配置（先清空再插入）"""

        # 插入新配置
        for request in mappings:
            # 先检测是否已存在
            exist = self.get_one({'scan_config_name': request.scan_config_name})
            if exist:
                self.update({'scan_config_name': request.scan_config_name}, request)
            else:
                self.create(request)
