import time
from typing import Dict, Optional, Any

from dbgpt.agent.resource import BaseTool, ToolParameter
from dbgpt.util.code.docker_code_executor import DockerCodeExecutor


class DockerCodeExecuteTool(BaseTool):
    """Tool for executing code in Docker containers asynchronously."""

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return "docker_code_execute"

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return "Execute code asynchronously in isolated Docker containers with support for multiple programming languages including Bash, Shell and Python."

    @property
    def args(self) -> Dict[str, ToolParameter]:
        """Return the arguments of the tool."""
        return {
            "code": ToolParameter(
                name="code",
                type="string",
                description="The code to execute"
            ),
            "language": ToolParameter(
                name="language",
                type="string",
                description="Programming language (python, bash, shell, sh)"
            ),
            # "container_id": ToolParameter(
            #     name="container_id",
            #     type="string",
            #     description="Container identifier for container reuse, it should be empty for the first time",
            #     required=False
            # ),
            "keep_container": ToolParameter(
                name="keep_container",
                type="boolean",
                description="Whether to keep the container after execution，if you need to execute other in future code keep it true",
                required=True
            )
        }

    @property
    def is_async(self) -> bool:
        """Return whether the resource is asynchronous."""
        return True

    def __init__(self, work_dirs=".", docker_manager=None, execution_timeout=60):
        """
        Initialize the Docker code execution tool.

        Args:
            work_dirs: Working directories to mount in the container
            docker_manager: AsyncDockerManager instance for container operations
            execution_timeout: Code execution timeout in seconds
        """
        super().__init__()

        # Set default work directory if not provided
        if work_dirs is None:
            import tempfile
            work_dirs = [tempfile.gettempdir()]

        # Initialize the AsyncDockerCodeExecutor
        self.executor = DockerCodeExecutor(
            work_dirs=work_dirs,
            docker_manager=docker_manager or DockerManager(network_enabled=False),
            execution_timeout=execution_timeout
        )


    async def async_execute(
        self, *args, resource_name: Optional[str] = None, **kwargs
    ) -> Any:
        """
        Execute code in a Docker container asynchronously.
        """
        # Extract parameters
        code = kwargs.get("code")
        language = kwargs.get("language")
        container_id = kwargs.get("container_id")
        keep_container = kwargs.get("keep_container", False)

        # Validate required parameters
        if not code:
            return {"error": "Code parameter is required"}
        if not language:
            return {"error": "Language parameter is required"}
        start_time = time.time()
        try:
            # Execute code using the Docker executor
            result = await self.executor.execute(
                code=code,
                language=language,
                container_id=container_id,
                keep_container=keep_container
            )

            # Return execution result as dictionary
            return {
                "container_id": result.container_id,
                "image": self.executor.docker_manager.image,
                "duration": f"{time.time() - start_time:.2f} seconds",
                "success": result.is_success(),
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def cleanup(self):
        """Clean up resources asynchronously."""
        await self.executor.cleanup()


import asyncio
from dbgpt.agent.resource import BaseTool
from examples.agents.tools.docker_code_executor_smart import DockerManager



async def main():
    # 创建Docker管理器，这里设置network_enabled=True允许容器连接网络
    docker_manager = DockerManager(network_enabled=True)

    # 初始化DockerCodeExecuteTool，设置工作目录和超时时间
    docker_tool = DockerCodeExecuteTool(
        work_dirs=".",  # 指定工作目录
        docker_manager=docker_manager,
        execution_timeout=120  # 设置120秒超时
    )

    # 示例1: 执行简单的Python代码
    python_code = """
print("Hello from Docker container!")
import os
print(f"Current working directory: {os.getcwd()}")
print(f"Files in directory: {os.listdir('.')}")
    """

    # 首次执行，不提供container_id
    result1 = await docker_tool.execute({
        "code": python_code,
        "language": "python",
        "keep_container": True  # 保留容器以便重用
    })

    print("示例1 - Python执行结果:")
    print(f"成功: {result1['success']}")
    print(f"标准输出:\n{result1['stdout']}")
    print(f"标准错误:\n{result1['stderr']}")
    print(f"会话ID: {result1['container_id']}")
    print("-" * 50)

    # 示例2: 在同一容器中执行Bash命令
    bash_code = """
echo "Executing bash commands..."
ls -la
echo "Creating a test file..."
echo "This is a test" > test.txt
cat test.txt
    """

    # 使用上一次执行返回的container_id继续使用同一容器
    result2 = await docker_tool.execute({
        "code": bash_code,
        "language": "bash",
        "container_id": result1['container_id'],  # 重用之前的容器
        "keep_container": True
    })

    print("示例2 - Bash执行结果:")
    print(f"成功: {result2['success']}")
    print(f"标准输出:\n{result2['stdout']}")
    print(f"标准错误:\n{result2['stderr']}")
    print("-" * 50)

    # 示例3: 再次执行Python代码验证文件持久性
    python_code2 = """
print("Checking if file created by bash exists...")
try:
    with open('test.txt', 'r') as f:
        content = f.read()
        print(f"File content: {content}")
except Exception as e:
    print(f"Error reading file: {e}")
    """

    result3 = await docker_tool.execute({
        "code": python_code2,
        "language": "python",
        "container_id": result1['container_id'],  # 继续使用同一容器
        "keep_container": False  # 执行完后销毁容器
    })

    print("示例3 - 文件持久性测试:")
    print(f"成功: {result3['success']}")
    print(f"标准输出:\n{result3['stdout']}")
    print(f"标准错误:\n{result3['stderr']}")
    print("-" * 50)

    # 清理资源
    await docker_tool.cleanup()


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())