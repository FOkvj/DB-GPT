from typing import Dict, Optional, Any

from dbgpt.agent import Resource
from dbgpt.agent.resource import ToolParameter, RDBMSConnectorResource, BaseTool

class RDBResourceTool(BaseTool):
    """To execute SQL statements on RDB resources."""

    def add_resource(self, resource: Resource):
        """Add a resource to the tool."""
        if not isinstance(resource, RDBMSConnectorResource):
            raise TypeError("Resource must be an instance of RDBMSConnectorResource")
        self.resources[f"{resource.db_type}:{resource.name}"] = resource

    @property
    def description(self) -> str:
        return "This is a tool to execute sql"

    @property
    def args(self) -> Dict[str, ToolParameter]:
        return {
            "resource_name": ToolParameter(
                type="string",
                name="resource_name",
                description="The name of the RDB resource to execute the SQL statement on. ",
            ),
            "db_type": ToolParameter(
                type="string",
                name="db_type",
                description="The type of the RDB resource (e.g., MySQL, PostgreSQL, etc.). "
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

    def execute(self, *args, resource_name: Optional[str] = None, **kwargs) -> Any:
        """Execute the resource."""
        self.get_resources()
        raise NotImplementedError



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
