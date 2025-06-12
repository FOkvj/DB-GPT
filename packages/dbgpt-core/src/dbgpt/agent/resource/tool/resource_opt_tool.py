from abc import ABC, abstractmethod
from dataclasses import Field
from typing import Dict, List

from dbgpt.agent import Resource

from dbgpt.agent.resource import BaseTool


class ResourceOptTool(BaseTool, ABC):
    resources: Dict[str, Resource]
    def __init__(self, **kwargs):
        """Initialize the ResourceOptTool."""
        super().__init__(**kwargs)
        self.resources: Dict[str, Resource] = {}

    @abstractmethod
    def init_resources(self, resources: List[Resource]):
        """Add a resource to the tool."""
