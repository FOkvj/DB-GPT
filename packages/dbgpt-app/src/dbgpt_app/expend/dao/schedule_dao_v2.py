from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, func


from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from dbgpt_app.expend.dao.data_manager import ExpendBaseDao, ExpendModel


# Pydantic schemas for request/response
class TaskConfigRequest(BaseModel):
    task_id: Optional[str] = None
    task_name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None


class TaskConfigResponse(BaseModel):
    id: Optional[int] = None
    task_id: str
    task_name: str
    description: Optional[str] = None
    enabled: bool = False
    interval_seconds: int = 60
    cron_expression: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskExecutionRequest(BaseModel):
    task_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None


class TaskExecutionResponse(BaseModel):
    id: Optional[int] = None
    task_id: str
    start_time: str
    end_time: Optional[str] = None
    status: str = 'running'
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: Optional[str] = None


# SQLAlchemy entities
class TaskConfigEntity(ExpendModel):
    __tablename__ = "task_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), unique=True, nullable=False)
    task_name = Column(String(200), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=False)
    interval_seconds = Column(Integer, default=60)
    cron_expression = Column(String(100))
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def __repr__(self):
        return (
            f"TaskConfigEntity(id={self.id}, task_id='{self.task_id}', "
            f"task_name='{self.task_name}', enabled={self.enabled}, "
            f"interval_seconds={self.interval_seconds})"
        )


class TaskExecutionEntity(ExpendModel):
    __tablename__ = "task_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    status = Column(String(20), default='running')
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    created_at = Column(DateTime, default=func.current_timestamp())

    def __repr__(self):
        return (
            f"TaskExecutionEntity(id={self.id}, task_id='{self.task_id}', "
            f"status='{self.status}', start_time='{self.start_time}')"
        )


# DAO classes
class TaskConfigDao(ExpendBaseDao[TaskConfigEntity, TaskConfigRequest, TaskConfigResponse]):

    def from_request(self, request: Union[TaskConfigRequest, Dict[str, Any]]) -> TaskConfigEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, TaskConfigRequest) else request
        )
        return TaskConfigEntity(**request_dict)

    def to_request(self, entity: TaskConfigEntity) -> TaskConfigRequest:
        """Convert an entity to a request"""
        return TaskConfigRequest(
            task_id=entity.task_id,
            task_name=entity.task_name,
            description=entity.description,
            enabled=entity.enabled,
            interval_seconds=entity.interval_seconds,
            cron_expression=entity.cron_expression,
        )

    def to_response(self, entity: TaskConfigEntity) -> TaskConfigResponse:
        """Convert an entity to a response"""
        created_at_str = entity.created_at.strftime("%Y-%m-%d %H:%M:%S") if entity.created_at else None
        updated_at_str = entity.updated_at.strftime("%Y-%m-%d %H:%M:%S") if entity.updated_at else None

        return TaskConfigResponse(
            id=entity.id,
            task_id=entity.task_id,
            task_name=entity.task_name,
            description=entity.description,
            enabled=entity.enabled,
            interval_seconds=entity.interval_seconds,
            cron_expression=entity.cron_expression,
            created_at=created_at_str,
            updated_at=updated_at_str,
        )

    def from_response(self, response: Union[TaskConfigResponse, Dict[str, Any]]) -> TaskConfigEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, TaskConfigResponse) else response
        )
        return TaskConfigEntity(**response_dict)

    def get_task_by_id(self, task_id: str) -> Optional[TaskConfigResponse]:
        """Get task config by task_id"""
        return self.get_one({"task_id": task_id})

    def get_all_tasks(self) -> List[TaskConfigResponse]:
        """Get all task configs"""
        return self.get_list({})

    def upsert_task(self, task_id: str, task_name: str, description: str = "",
                    enabled: bool = False, interval_seconds: int = 60) -> TaskConfigResponse:
        """Insert or update task config"""
        existing = self.get_task_by_id(task_id)

        if existing:
            # Update existing task
            update_request = TaskConfigRequest(
                task_name=task_name,
                description=description,
                enabled=enabled,
                interval_seconds=interval_seconds,
            )
            return self.update({"task_id": task_id}, update_request)
        else:
            # Create new task
            create_request = TaskConfigRequest(
                task_id=task_id,
                task_name=task_name,
                description=description,
                enabled=enabled,
                interval_seconds=interval_seconds,
            )
            return self.create(create_request)

    def update_task_status(self, task_id: str, enabled: bool) -> Optional[TaskConfigResponse]:
        """Update task enabled status"""
        try:
            update_request = TaskConfigRequest(enabled=enabled)
            return self.update({"task_id": task_id}, update_request)
        except Exception:
            return None

    def update_task_interval(self, task_id: str, interval_seconds: int) -> Optional[TaskConfigResponse]:
        """Update task execution interval"""
        try:
            update_request = TaskConfigRequest(interval_seconds=interval_seconds)
            return self.update({"task_id": task_id}, update_request)
        except Exception:
            return None


class TaskExecutionDao(ExpendBaseDao[TaskExecutionEntity, TaskExecutionRequest, TaskExecutionResponse]):

    def from_request(self, request: Union[TaskExecutionRequest, Dict[str, Any]]) -> TaskExecutionEntity:
        """Convert a request to an entity"""
        request_dict = (
            request.dict() if isinstance(request, TaskExecutionRequest) else request
        )
        return TaskExecutionEntity(**request_dict)

    def to_request(self, entity: TaskExecutionEntity) -> TaskExecutionRequest:
        """Convert an entity to a request"""
        return TaskExecutionRequest(
            task_id=entity.task_id,
            start_time=entity.start_time,
            end_time=entity.end_time,
            status=entity.status,
            error_message=entity.error_message,
            execution_time_ms=entity.execution_time_ms,
        )

    def to_response(self, entity: TaskExecutionEntity) -> TaskExecutionResponse:
        """Convert an entity to a response"""
        start_time_str = entity.start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = entity.end_time.strftime("%Y-%m-%d %H:%M:%S") if entity.end_time else None
        created_at_str = entity.created_at.strftime("%Y-%m-%d %H:%M:%S") if entity.created_at else None

        return TaskExecutionResponse(
            id=entity.id,
            task_id=entity.task_id,
            start_time=start_time_str,
            end_time=end_time_str,
            status=entity.status,
            error_message=entity.error_message,
            execution_time_ms=entity.execution_time_ms,
            created_at=created_at_str,
        )

    def from_response(self, response: Union[TaskExecutionResponse, Dict[str, Any]]) -> TaskExecutionEntity:
        """Convert a response to an entity"""
        response_dict = (
            response.dict() if isinstance(response, TaskExecutionResponse) else response
        )
        return TaskExecutionEntity(**response_dict)

    def log_execution(self, task_id: str, status: str, start_time: datetime,
                      end_time: datetime = None, error_message: str = None) -> Optional[TaskExecutionResponse]:
        """Log task execution"""
        execution_time_ms = None
        if end_time and start_time:
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        try:
            request = TaskExecutionRequest(
                task_id=task_id,
                start_time=start_time,
                end_time=end_time,
                status=status,
                error_message=error_message,
                execution_time_ms=execution_time_ms,
            )
            return self.create(request)
        except Exception:
            return None
