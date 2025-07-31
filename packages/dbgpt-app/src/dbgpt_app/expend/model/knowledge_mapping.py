from typing import List

from dbgpt._private.pydantic import BaseModel, Field
class KnowledgeBaseMappingConfig(BaseModel):
    id: int = Field(None, alias="id")
    scan_config_name: str = None
    knowledge_base_id: str = None
    knowledge_base_name: str = None
    enabled: bool = True

class KnowledgeBaseMappingRequest(BaseModel):
    mappings: List[KnowledgeBaseMappingConfig]