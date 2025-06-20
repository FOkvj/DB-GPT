
import functools
from typing import Dict, Callable, Optional


class TaskRegistry:
    """任务注册器"""
    _tasks: Dict[str, dict] = {}

    @classmethod
    def register(cls, task_id: str, name: str, description: str = "",
                 default_interval: int = 60, default_enabled: bool = False):
        """任务注册装饰器"""

        def decorator(func: Callable):
            cls._tasks[task_id] = {
                'func': func,
                'task_id': task_id,
                'name': name,
                'description': description,
                'default_interval': default_interval,
                'default_enabled': default_enabled
            }

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    @classmethod
    def get_task(cls, task_id: str) -> Optional[dict]:
        """获取注册的任务"""
        return cls._tasks.get(task_id)

    @classmethod
    def get_all_tasks(cls) -> Dict[str, dict]:
        """获取所有注册的任务"""
        return cls._tasks.copy()

    @classmethod
    def get_task_function(cls, task_id: str) -> Optional[Callable]:
        """获取任务函数"""
        task = cls._tasks.get(task_id)
        return task['func'] if task else None


# 任务注册装饰器
task = TaskRegistry.register