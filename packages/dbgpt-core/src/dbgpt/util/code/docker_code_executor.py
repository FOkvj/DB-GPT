import io
import logging
import tarfile
from abc import ABC, abstractmethod
from typing import List, Optional, Union

import docker
from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    """
    Class representing the result of a code execution.
    Inherits from Pydantic BaseModel for validation and serialization.
    """

    exit_code: int = Field(
        description="Exit code from command execution"
    )
    container_id: str = Field(
        default=None,
        description="Container ID"
    )
    stdout: str = Field(
        default="",
        description="Standard output content"
    )
    stderr: str = Field(
        default="",
        description="Standard error content"
    )

    def is_success(self) -> bool:
        """
        Check if execution was successful

        Returns:
            True if exit code is 0, False otherwise
        """
        return self.exit_code == 0


class CodeExecutor(ABC):
    """
    Abstract base class for code executors.
    Defines the minimal interface that all code executors must implement.
    """

    def __init__(self, log_level: str = 'INFO'):
        """
        Initialize the code executor

        Args:
            log_level: Logging level
        """
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def execute(self, code: str, language: str, **kwargs) -> ExecutionResult:
        """
        Execute code asynchronously

        Args:
            code: Code to execute
            language: Programming language
            **kwargs: Additional parameters specific to the executor implementation

        Returns:
            ExecutionResult object containing exit_code, stdout, and stderr
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """
        Clean up resources asynchronously
        """
        pass


class DockerManager:
    """
    Asynchronous Docker container manager that handles three main operations:
    1. Create container
    2. Get container by session ID
    3. Destroy container

    Includes a timeout mechanism to automatically destroy containers that haven't
    been accessed for a specified period of time.
    """

    def __init__(
            self,
            image: str = "python:3.9-slim",
            memory_limit: str = '256m',
            cpu_limit: float = 1.0,
            network_enabled: bool = False,
            log_level: str = 'INFO',
            container_timeout: int = 30,  # Default timeout: 30 seconds
            cleanup_interval: int = 15  # Default cleanup interval: 30 seconds
    ):
        """
        Initialize Docker container manager

        Args:
            image: Docker image name
            memory_limit: Memory limit, e.g. '512m', '1g'
            cpu_limit: CPU limit, e.g. 0.5, 1.0, 2.0
            network_enabled: Whether to allow container network access
            log_level: Logging level
            container_timeout: Time in seconds after which an inactive container is destroyed
            cleanup_interval: Interval in seconds for checking and cleaning up inactive containers
        """
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize Docker client
        try:
            self.client = docker.from_env()
            self.logger.info("Successfully connected to Docker service")
        except Exception as e:
            self.logger.error(f"Failed to connect to Docker service: {e}")
            raise

        # Set Docker related parameters
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled

        # Container registry - stores the container objects
        self.containers = {}

        # Container last access time registry
        self.last_access_times: Dict[str, float] = {}

        # Container timeout settings
        self.container_timeout = container_timeout
        self.cleanup_interval = cleanup_interval

        # Flag to control the cleanup task
        self.cleanup_task_running = False
        self.cleanup_task = None

    async def start_cleanup_task(self):
        """
        Start the periodic cleanup task if not already running
        """
        if not self.cleanup_task_running:
            self.cleanup_task_running = True
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self.logger.info(
                f"Started container cleanup task (interval: {self.cleanup_interval}s, timeout: {self.container_timeout}s)")

    async def stop_cleanup_task(self):
        """
        Stop the periodic cleanup task if running
        """
        if self.cleanup_task_running and self.cleanup_task:
            self.cleanup_task_running = False
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Stopped container cleanup task")

    async def _periodic_cleanup(self):
        """
        Periodically check for and destroy inactive containers
        """
        try:
            while self.cleanup_task_running:
                await self._cleanup_inactive_containers()
                await asyncio.sleep(self.cleanup_interval)
        except asyncio.CancelledError:
            self.logger.debug("Cleanup task cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error in cleanup task: {e}")
            # Restart the task if it fails
            if self.cleanup_task_running:
                self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _cleanup_inactive_containers(self):
        """
        Clean up containers that have been inactive for longer than the timeout
        """
        current_time = time.time()
        inactive_sessions = []

        # Find inactive sessions
        for container_id, last_access in list(self.last_access_times.items()):
            if current_time - last_access > self.container_timeout:
                inactive_sessions.append(container_id)

        # Destroy inactive containers
        if inactive_sessions:
            self.logger.info(f"Found {len(inactive_sessions)} inactive containers to clean up")
            for container_id in inactive_sessions:
                await self.destroy_container(container_id)
                self.logger.info(f"Destroyed inactive container for session: {container_id}")

    async def get_or_create_container(
            self,
            container_id: str = None,
            work_dirs: List[str] = None
    ):
        """
        Get an existing container or create a new one if it doesn't exist
        Updates the last access time for the session

        Args:
            container_id: Container identifier
            work_dirs: List of working directories to mount (only used if container is created)

        Returns:
            Container object

        Raises:
            ValueError: If container doesn't exist and work_dirs is None
        """
        # Start the cleanup task if not already running
        if not self.cleanup_task_running:
            await self.start_cleanup_task()

        # If container_id is None, try to select a random container from existing ones
        if container_id is None:
            if self.containers:
                # Get a random container_id from existing containers
                import random
                container_id = random.choice(list(self.containers.keys()))
                self.logger.info(f"No container_id provided, randomly selected: {container_id}")
            else:
                # No existing containers and no container_id, generate a new one
                container_id = str(uuid.uuid4())
                self.logger.info(f"No container_id provided and no existing containers, generated: {container_id}")

        # Update last access time
        self.last_access_times[container_id] = time.time()

        # Try to get existing container
        if container_id in self.containers:
            # Refresh container state - put this in a thread to avoid blocking
            await asyncio.to_thread(self.containers[container_id].reload)
            self.logger.debug(f"Using existing container for session: {container_id}")
            return self.containers[container_id]

        # Try to find container by name pattern
        container_name = f"executor-{container_id}"
        try:
            # Run container lookup in a thread to avoid blocking
            container = await asyncio.to_thread(self.client.containers.get, container_name)
            # Add to registry
            self.containers[container_id] = container
            self.logger.debug(f"Found existing container for session: {container_id}")
            return container
        except docker.errors.NotFound:
            # Container doesn't exist, create a new one if work_dirs is provided
            if work_dirs is None:
                raise ValueError(
                    f"Container not found for session: {container_id} and no work_dirs provided for creation")

            # Prepare volume bindings for work directories
            binds = {}
            for i, dir_path in enumerate(work_dirs):
                container_path = f"/workspace/{i}"
                binds[os.path.abspath(dir_path)] = {'bind': container_path, 'mode': 'rw'}

            # Set network mode
            network_mode = 'bridge' if self.network_enabled else 'none'

            # Command to keep container running
            command = "tail -f /dev/null"

            # Create container - run in a thread to avoid blocking
            self.logger.info(f"Creating new container: {container_name} for session {container_id}")

            container = await asyncio.to_thread(
                self.client.containers.create,
                image=self.image,
                command=command,
                volumes=binds,
                name=container_name,
                network_mode=network_mode,
                mem_limit=self.memory_limit,
                nano_cpus=int(self.cpu_limit * 1e9),  # Convert to nano CPUs
                detach=True,
                working_dir="/workspace/0" if binds else None
            )

            # Start container - run in a thread to avoid blocking
            await asyncio.to_thread(container.start)

            # Save container reference
            self.containers[container_id] = container

            return container

    async def destroy_container(self, container_id: str) -> None:
        """
        Destroy container by session ID

        Args:
            container_id: Container identifier
        """
        if container_id not in self.containers:
            self.logger.warning(f"Container not found for session: {container_id}")
            return

        container = self.containers[container_id]

        try:
            # Stop and remove container - run in a thread to avoid blocking
            self.logger.info(f"Destroying container for session: {container_id}")
            await asyncio.to_thread(container.remove, force=True)

            # Remove from registry
            del self.containers[container_id]

            # Remove from last access times
            if container_id in self.last_access_times:
                del self.last_access_times[container_id]

        except Exception as e:
            self.logger.error(f"Error destroying container for session {container_id}: {e}")
            # Still remove from registry
            if container_id in self.containers:
                del self.containers[container_id]
            if container_id in self.last_access_times:
                del self.last_access_times[container_id]

    async def cleanup(self) -> None:
        """
        Clean up all containers and stop the cleanup task
        """
        self.logger.info("Cleaning up all containers")

        # Stop the cleanup task
        await self.stop_cleanup_task()

        # Create tasks for all container destructions
        tasks = []
        for container_id in list(self.containers.keys()):
            tasks.append(self.destroy_container(container_id))

        # Wait for all destruction tasks to complete
        if tasks:
            await asyncio.gather(*tasks)

        # Clear the last access times
        self.last_access_times.clear()

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_cleanup_task()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure resources are properly cleaned up"""
        await self.cleanup()


class DockerCodeExecutor(CodeExecutor):
    """
    Asynchronous Docker-based code executor, supporting multiple programming languages.
    Uses DockerManager for container operations.
    """

    # Supported languages and their corresponding commands
    SUPPORTED_LANGUAGES = {
        'bash': '/bin/bash',
        'shell': '/bin/sh',
        'sh': '/bin/sh',
        'python': 'python',
    }

    def __init__(
            self,
            work_dirs: Union[str, List[str]],
            docker_manager: Optional[DockerManager] = None,
            image: str = "python:3.9-slim",
            log_level: str = 'INFO',
            execution_timeout: int = 60,
            container_timeout: int = 1800  # Default container timeout: 30 minutes
    ):
        """
        Initialize Docker code executor

        Args:
            work_dirs: Path to working directories, can be a single string or list of strings
            docker_manager: DockerManager instance, if None will create a new one
            image: Default Docker image name
            log_level: Logging level
            execution_timeout: Code execution timeout in seconds
            container_timeout: Time in seconds after which an inactive container is destroyed
        """
        # Call parent class initialization
        super().__init__(log_level)

        # Normalize working directories
        if isinstance(work_dirs, str):
            work_dirs = [work_dirs]

        # Validate that working directories exist
        for work_dir in work_dirs:
            if not os.path.exists(work_dir):
                self.logger.error(f"Working directory does not exist: {work_dir}")
                raise ValueError(f"Working directory does not exist: {work_dir}")

        self.work_dirs = [os.path.abspath(dir_path) for dir_path in work_dirs]
        self.logger.info(f"Set working directories: {self.work_dirs}")

        # Set execution timeout
        self.execution_timeout = execution_timeout

        # Use provided docker manager or create a new one
        if docker_manager is None:
            self.docker_manager = DockerManager(
                image=image,
                log_level=log_level,
                container_timeout=container_timeout
            )
        else:
            self.docker_manager = docker_manager

    def _validate_language(self, language: str) -> None:
        """
        Validate if the language is supported

        Args:
            language: Language name

        Raises:
            ValueError: If language is not supported
        """
        if language not in self.SUPPORTED_LANGUAGES:
            supported = ", ".join(self.SUPPORTED_LANGUAGES.keys())
            raise ValueError(f"Unsupported language: {language}, supported languages are: {supported}")

    async def _create_tar_archive(self, script_path, script_filename):
        """
        Create a tar archive for the script file

        Args:
            script_path: Path to the script file
            script_filename: Name of the script file

        Returns:
            Bytes containing the tar archive
        """
        # Read script file
        with open(script_path, 'rb') as src_file:
            data = src_file.read()

        # Create a tarfile with correct structure
        tar_stream = io.BytesIO()
        tar = tarfile.open(fileobj=tar_stream, mode='w')

        # Create a TarInfo object
        tarinfo = tarfile.TarInfo(name=script_filename)
        tarinfo.size = len(data)

        # Add the file data to the tarfile
        tar.addfile(tarinfo, io.BytesIO(data))
        tar.close()

        # Reset the stream position
        tar_stream.seek(0)

        return tar_stream.read()

    async def execute(
            self,
            code: str,
            language: str,
            container_id: str = None,
            keep_container: bool = False,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute code asynchronously

        Args:
            code: Code to execute
            language: Programming language
            container_id: Container identifier for container reuse
            keep_container: Whether to keep the container after execution
            **kwargs: Additional parameters (not used in this implementation)

        Returns:
            ExecutionResult object containing container_id, exit_code, stdout, and stderr
        """
        # Check if language is supported
        self._validate_language(language)

        # Get command for the language
        command = self.SUPPORTED_LANGUAGES[language]

        # Get or create container
        try:
            container = await self.docker_manager.get_or_create_container(container_id, self.work_dirs)
            # Container was either retrieved or created successfully
            container_exists = True
        except Exception as e:
            self.logger.error(f"Failed to get or create container: {e}")
            return ExecutionResult(container_id=container_id, exit_code=-1, stdout="", stderr=f"Container error: {str(e)}")

        # Use temporary file to store code
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as f:
            f.write(code)
            script_path = f.name

        try:
            # Get filename of the temporary file
            script_filename = os.path.basename(script_path)

            # Container path for the script
            container_script_path = f"/tmp/{script_filename}"

            # Create tar archive
            tar_data = await self._create_tar_archive(script_path, script_filename)

            # Upload the tar archive to the container - run in a thread to avoid blocking
            await asyncio.to_thread(container.put_archive, '/tmp', tar_data)

            # Prepare execution command
            exec_command = f"{command} {container_script_path}"

            # Execute command in container
            self.logger.info(f"Executing {language} code in container for session {container_id}")

            # Execute command with timeout - run in a thread to avoid blocking
            result = await asyncio.to_thread(
                container.exec_run,
                cmd=exec_command,
                stderr=True,
                stdout=True,
                demux=True
            )

            exit_code = result.exit_code

            # Process output
            output = result.output
            # Handle potential format differences in the output
            if isinstance(output, tuple) and len(output) >= 2:
                # output is already a tuple of (stdout, stderr)
                stdout = output[0].decode('utf-8', errors='replace') if output[0] else ""
                stderr = output[1].decode('utf-8', errors='replace') if output[1] else ""
            elif isinstance(output, bytes):
                # output is a single bytes object
                stdout = output.decode('utf-8', errors='replace')
                stderr = ""
            else:
                # Fallback for other unexpected formats
                stdout = str(output)
                stderr = ""

            # Handle container cleanup if needed
            if not keep_container:
                # Schedule cleanup but don't wait for it
                asyncio.create_task(self.docker_manager.destroy_container(container_id))

            return ExecutionResult(container_id=container_id or "", exit_code=exit_code, stdout=stdout, stderr=stderr)

        except Exception as e:
            self.logger.error(f"Error executing code: {e}")
            # Clean up container if we created it but don't want to keep it
            if not container_exists and not keep_container:
                # Schedule cleanup but don't wait for it
                asyncio.create_task(self.docker_manager.destroy_container(container_id))
            # Return execution result with error
            return ExecutionResult(container_id=container_id, exit_code=-1, stdout="", stderr=str(e))

        finally:
            # Clean up temporary file
            if os.path.exists(script_path):
                os.unlink(script_path)

    async def cleanup(self) -> None:
        """
        Clean up resources asynchronously
        """
        await self.docker_manager.cleanup()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure resources are properly cleaned up"""
        await self.cleanup()


import os
import tempfile
import uuid
import asyncio
import time

# Import from the existing module
from typing import List, Union, Dict


class LocalCodeExecutor(CodeExecutor):
    """
    Asynchronous Local code executor, supporting multiple programming languages.
    Runs code directly on the local machine.
    """

    # Supported languages and their corresponding commands
    SUPPORTED_LANGUAGES = {
        'bash': '/bin/bash',
        'shell': '/bin/sh',
        'sh': '/bin/sh',
        'python': 'python',
    }

    def __init__(
            self,
            work_dirs: Union[str, List[str]],
            log_level: str = 'INFO',
            execution_timeout: int = 60,
    ):
        """
        Initialize Local code executor

        Args:
            work_dirs: Path to working directories, can be a single string or list of strings
            log_level: Logging level
            execution_timeout: Code execution timeout in seconds
        """
        # Call parent class initialization
        super().__init__(log_level)

        # Normalize working directories
        if isinstance(work_dirs, str):
            work_dirs = [work_dirs]

        # Validate that working directories exist
        for work_dir in work_dirs:
            if not os.path.exists(work_dir):
                self.logger.error(f"Working directory does not exist: {work_dir}")
                raise ValueError(f"Working directory does not exist: {work_dir}")

        self.work_dirs = [os.path.abspath(dir_path) for dir_path in work_dirs]
        self.logger.info(f"Set working directories: {self.work_dirs}")

        # Set execution timeout
        self.execution_timeout = execution_timeout

        # Track active processes for cleanup
        self.active_processes = {}

    def _validate_language(self, language: str) -> None:
        """
        Validate if the language is supported

        Args:
            language: Language name

        Raises:
            ValueError: If language is not supported
        """
        if language not in self.SUPPORTED_LANGUAGES:
            supported = ", ".join(self.SUPPORTED_LANGUAGES.keys())
            raise ValueError(f"Unsupported language: {language}, supported languages are: {supported}")

    async def execute(
            self,
            code: str,
            language: str,
            container_id: str = None,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute code asynchronously on the local machine

        Args:
            code: Code to execute
            language: Programming language
            container_id: Container identifier (optional, for API compatibility with DockerCodeExecutor)
            **kwargs: Additional parameters (not used in this implementation)

        Returns:
            ExecutionResult object containing container_id, exit_code, stdout, and stderr
        """
        # Check if language is supported
        self._validate_language(language)

        # Get command for the language
        command = self.SUPPORTED_LANGUAGES[language]

        # Generate session ID if not provided
        if container_id is None:
            container_id = str(uuid.uuid4())

        # Use temporary file to store code
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as f:
            f.write(code)
            script_path = f.name

        try:
            # Prepare execution command
            exec_command = [command, script_path]

            # Set the working directory to the first work directory
            working_dir = self.work_dirs[0] if self.work_dirs else None

            self.logger.info(f"Executing {language} code locally for session {container_id}")

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *exec_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )

            # Store process for potential cleanup
            self.active_processes[container_id] = process

            try:
                # Execute with timeout
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.execution_timeout
                )

                # Process output
                stdout = stdout_bytes.decode('utf-8', errors='replace')
                stderr = stderr_bytes.decode('utf-8', errors='replace')
                exit_code = process.returncode

            except asyncio.TimeoutError:
                # Timeout occurred, terminate the process
                self.logger.warning(f"Execution timeout for session {container_id}")

                # Try to terminate the process gracefully
                process.terminate()
                try:
                    # Wait a short time for it to terminate
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    # If it doesn't terminate gracefully, kill it
                    self.logger.warning(f"Forcefully killing process for session {container_id}")
                    process.kill()
                    await process.wait()  # Ensure process is fully cleaned up

                stdout = ""
                stderr = "Execution timed out"
                exit_code = -1

            # Remove from active processes
            if container_id in self.active_processes:
                del self.active_processes[container_id]

            return ExecutionResult(
                container_id=container_id,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr
            )

        except Exception as e:
            self.logger.error(f"Error executing code: {e}")
            # Return execution result with error
            return ExecutionResult(
                container_id=container_id,
                exit_code=-1,
                stdout="",
                stderr=str(e)
            )

        finally:
            # Clean up temporary file
            if os.path.exists(script_path):
                os.unlink(script_path)

    async def cleanup(self) -> None:
        """
        Clean up resources asynchronously by terminating any active processes
        """
        self.logger.info("Cleaning up local code executor resources")

        # Terminate all active processes
        for container_id, process in list(self.active_processes.items()):
            self.logger.info(f"Terminating process for session {container_id}")
            try:
                # Try to terminate gracefully
                process.terminate()
                try:
                    # Wait a short time for it to terminate
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    # If it doesn't terminate gracefully, kill it
                    self.logger.warning(f"Forcefully killing process for session {container_id}")
                    process.kill()
                    await process.wait()  # Ensure process is fully cleaned up
            except Exception as e:
                self.logger.error(f"Error terminating process for session {container_id}: {e}")

            # Remove from active processes
            if container_id in self.active_processes:
                del self.active_processes[container_id]

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure resources are properly cleaned up"""
        await self.cleanup()


# Example usage
async def local_executor_example():
    """Example usage of LocalCodeExecutor"""
    # Create the local executor
    local_executor = LocalCodeExecutor(
        work_dirs=["."],
        execution_timeout=30
    )

    # Python code example
    python_code = """
import os
import sys
import time
print("Hello from Local Executor!")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Directory contents: {os.listdir('.')}")
"""

    # Execute the code
    result = await local_executor.execute(
        code=python_code,
        language="python"
    )

    print("Local Execution Results:")
    print(f"Session ID: {result.container_id}")
    print(f"Success: {result.is_success()}")
    print(f"Exit code: {result.exit_code}")
    print(f"Output:\n{result.stdout}")
    if result.stderr:
        print(f"Errors:\n{result.stderr}")

    # Shell example with a specific session ID
    shell_code = "echo 'Running a shell command from local executor'"
    container_id = "local_session"
    shell_result = await local_executor.execute(
        code=shell_code,
        language="shell",
        container_id=container_id
    )

    print("\nShell Execution Results:")
    print(f"Session ID: {shell_result.container_id}")
    print(f"Success: {shell_result.is_success()}")
    print(f"Exit code: {shell_result.exit_code}")
    print(f"Output:\n{shell_result.stdout}")
    if shell_result.stderr:
        print(f"Errors:\n{shell_result.stderr}")

    # Example with timeout
    timeout_code = """
import time
print("Starting long operation...")
time.sleep(60)  # This should trigger a timeout if execution_timeout is less than 60
print("This line should not be printed due to timeout")
"""
    timeout_result = await local_executor.execute(
        code=timeout_code,
        language="python"
    )

    print("\nTimeout Execution Results:")
    print(f"Session ID: {timeout_result.container_id}")
    print(f"Success: {timeout_result.is_success()}")
    print(f"Exit code: {timeout_result.exit_code}")
    print(f"Output:\n{timeout_result.stdout}")
    if timeout_result.stderr:
        print(f"Errors:\n{timeout_result.stderr}")

    # Clean up resources
    await local_executor.cleanup()


if __name__ == "__main__":
    # Run the example
    asyncio.run(local_executor_example())
# Usage Example
async def main():
    """Example usage of DockerCodeExecutor with container timeout"""
    # Create an async Docker manager with container timeout of 5 minutes
    # and cleanup interval of 1 minute for demonstration purposes
    docker_manager = DockerManager(
        network_enabled=True,
        container_timeout=3,  # 5 minutes
        cleanup_interval=2  # 1 minute
    )

    # Create an async Docker executor
    docker_executor = DockerCodeExecutor(
        docker_manager=docker_manager,
        work_dirs=["."],
        execution_timeout=30
    )

    # Execute Python code example with Docker
    python_code = """
import os
import sys
import time
time.sleep(5)
print("Hello from Async Docker!")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Directory contents: {os.listdir('.')}")
"""

    # Execute with a new session, don't keep container
    docker_result = await docker_executor.execute(
        code=python_code,
        language="python"
    )

    print("Docker Execution Results:")
    print(f"Session ID: {docker_result.container_id}")
    print(f"Success: {docker_result.is_success()}")
    print(f"Exit code: {docker_result.exit_code}")
    print(f"Output:\n{docker_result.stdout}")
    if docker_result.stderr:
        print(f"Errors:\n{docker_result.stderr}")

    # Execute shell code with specific session and keep container
    container_id = "my_async_session"
    shell_code = "echo 'This container will timeout after 5 minutes of inactivity'"
    shell_result = await docker_executor.execute(
        code=shell_code,
        language="shell",
        container_id=container_id,
        keep_container=True
    )

    print("\nShell Execution Results:")
    print(f"Session ID: {shell_result.container_id}")
    print(f"Success: {shell_result.is_success()}")
    print(f"Exit code: {shell_result.exit_code}")
    print(f"Output:\n{shell_result.stdout}")
    if shell_result.stderr:
        print(f"Errors:\n{shell_result.stderr}")

    # Wait for a while to see container timeout in action
    print("\nWaiting for 10 seconds to simulate inactivity...")
    await asyncio.sleep(10)

    # Execute another command in the same container
    print("\nExecuting another command in the same container...")
    shell_result2 = await docker_executor.execute(
        code="ls -la /tmp",
        language="shell",
        container_id=container_id
    )

    print("Shell Execution Results:")
    print(f"Session ID: {shell_result2.container_id}")
    print(f"Success: {shell_result2.is_success()}")
    print(f"Exit code: {shell_result2.exit_code}")
    print(f"Output:\n{shell_result2.stdout}")
    if shell_result2.stderr:
        print(f"Errors:\n{shell_result2.stderr}")

    # Let container timeout - comment out this line to see the cleanup in action
    # print("\nWaiting for container timeout (5 minutes)...")
    # await asyncio.sleep(310)  # Wait a bit more than the timeout period (5 minutes + 10 seconds)

    # Clean up Docker resources
    print("\nCleaning up resources...")
    await docker_executor.cleanup()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())