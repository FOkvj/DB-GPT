import logging
from typing import Dict, Optional, Any, List

from dbgpt_serve.agent.resource.datasource import DatasourceResource

from dbgpt.agent import Resource
from dbgpt.agent.resource import ToolParameter, RDBMSConnectorResource, DBResource
from dbgpt.agent.resource.tool.resource_opt_tool import ResourceOptTool

logger = logging.getLogger(__name__)

class RDBResourceTool(ResourceOptTool):
    """To execute SQL statements on RDB resources."""

    def _add_resource(self, resource: DatasourceResource):
        """Add a resource to the tool."""
        self.resources[self._make_key(resource.db_type, resource.db_name)] = resource
    def init_resources(self, resources: List[Resource]):
        """Initialize the RDB resources from the provided list."""

        for resource in resources:
            if isinstance(resource, DatasourceResource):
                self._add_resource(resource)
            else:
                logger.warning("Resource is not a valid DatasourceResource, skipping.")
    def _make_key(self, db_type: Optional[str], db_name: Optional[str] = None) -> str:
        return f"rdb:{db_type}:{db_name}" if db_name else f"rdb:{db_type}"
    @property
    def description(self) -> str:
        return "This is a tool to execute sql"

    @property
    def args(self) -> Dict[str, ToolParameter]:
        return {
            "db_name": ToolParameter(
                type="string",
                name="db_name",
                description="The database name",
            ),
            "db_type": ToolParameter(
                type="string",
                name="db_type",
                description="The type of the RDB resource"
            ),
            "sql": ToolParameter(
                type="string",
                name="sql",
                description="The SQL statement to be executed on the RDB resource.",
            ),
            "display_type": ToolParameter(
                type="string",
                name="display_type",
                description="The maximum number of rows to return from the SQL query.",
            )
        }

    @property
    def name(self) -> str:
        return "sql_executor"
    def is_async(self) -> bool:
        return True

    async def async_execute(self, *args, resource_name: Optional[str] = None, **kwargs) -> Any:
        """Execute the resource."""
        return await self._do_query(**kwargs)

    async def _do_query(self, db_name: str, sql: str, db_type:str, display_type: Optional[str] = None) -> Any:
        """Execute the SQL query on the specified RDB resource."""
        resource: DatasourceResource = self.resources.get(self._make_key(db_type, db_name))
        result = await resource.query(sql)
        return result[:10]



if __name__ == "__main__":
    # Example usage
    tool = RDBResourceTool()
    # print(tool.description)
    # print(tool.args)
    # print(tool.name)

    tool.add_resource(RDBMSConnectorResource("DatabaseResource1"))

    # Note: The execute method is not implemented, so it will raise NotImplementedError
    try:
        tool.execute()
    except NotImplementedError as e:
        print(e)
