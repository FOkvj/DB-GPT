"""
SchedulerManager重构为Service层，直接使用DAO操作数据库
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from dbgpt import BaseComponent
from dbgpt.component import ComponentType, SystemApp
from dbgpt.storage.metadata import db
from dbgpt_app.expend.dao.schedule_dao_v2 import TaskConfigDao, TaskExecutionDao, TaskConfigRequest, \
    TaskExecutionRequest
from dbgpt_app.expend.decorators.schedule_decorator import TaskRegistry, task


class SchedulerManager(BaseComponent):
    """调度器管理器 - Service层"""

    name = ComponentType.SCHEDULE_MANAGER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        """初始化调度器管理器"""
        self.scheduler = BackgroundScheduler()

        # 使用DAO层操作数据库
        self.task_config_dao = TaskConfigDao()
        self.task_execution_dao = TaskExecutionDao()

        # 确保数据库已初始化
        self._ensure_database_initialized()

    def _ensure_database_initialized(self):
        """确保数据库已初始化"""
        if not db.is_initialized:
            # 如果db未初始化，使用默认配置
            db.init_default_db("scheduler.db")
            db.create_all()
            print("数据库已自动初始化")

    def init_app(self, system_app: SystemApp):
        """初始化应用"""
        pass

    def start(self):
        """启动调度器并初始化任务"""
        self._sync_registered_tasks()
        self._load_and_start_tasks()
        self.scheduler.start()
        print("调度器已启动")

    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("调度器已关闭")

    def _sync_registered_tasks(self):
        """同步注册的任务到数据库"""
        registered_tasks = TaskRegistry.get_all_tasks()
        for task_id, task_info in registered_tasks.items():
            try:
                # 检查任务是否已存在
                existing_task = self.task_config_dao.get_one({"task_id": task_id})

                if existing_task:
                    # 任务已存在，只更新名称和描述，保持用户的启用状态和间隔设置
                    update_request = TaskConfigRequest(
                        task_name=task_info['name'],
                        description=task_info['description']
                    )
                    self.task_config_dao.update({"task_id": task_id}, update_request)
                    print(f"已更新任务信息: {task_id}")
                else:
                    # 创建新任务
                    create_request = TaskConfigRequest(
                        task_id=task_id,
                        task_name=task_info['name'],
                        description=task_info['description'],
                        enabled=task_info['default_enabled'],
                        interval_seconds=task_info['default_interval']
                    )
                    self.task_config_dao.create(create_request)
                    print(f"已创建新任务: {task_id}")

            except Exception as e:
                print(f"同步任务 {task_id} 失败: {e}")

    def _load_and_start_tasks(self):
        """从数据库加载并启动启用的任务"""
        try:
            enabled_tasks = self.task_config_dao.get_list({"enabled": True})
            for task_response in enabled_tasks:
                self._add_job(task_response.task_id, task_response.interval_seconds)
        except Exception as e:
            print(f"加载任务失败: {e}")

    def _add_job(self, task_id: str, interval_seconds: int) -> bool:
        """添加定时任务"""
        task_func = TaskRegistry.get_task_function(task_id)
        if not task_func:
            print(f"未找到注册的任务函数: {task_id}")
            return False

        try:
            # 如果任务已存在，先移除
            if self.scheduler.get_job(task_id):
                self.scheduler.remove_job(task_id)

            # 创建包装函数，用于记录执行历史
            def wrapped_task():
                start_time = datetime.now()
                try:
                    task_func()
                    end_time = datetime.now()
                    self._log_execution(task_id, 'success', start_time, end_time)
                except Exception as e:
                    end_time = datetime.now()
                    error_msg = str(e)
                    print(f"任务 {task_id} 执行失败: {error_msg}")
                    self._log_execution(task_id, 'failed', start_time, end_time, error_msg)

            # 添加任务
            self.scheduler.add_job(
                func=wrapped_task,
                trigger=IntervalTrigger(seconds=interval_seconds),
                id=task_id,
                name=f"Task_{task_id}"
            )
            print(f"任务 {task_id} 已添加，间隔: {interval_seconds}秒")
            return True

        except Exception as e:
            print(f"添加任务 {task_id} 失败: {e}")
            return False

    def _log_execution(self, task_id: str, status: str, start_time: datetime,
                       end_time: datetime = None, error_message: str = None):
        """记录任务执行历史"""
        try:
            execution_time_ms = None
            if end_time and start_time:
                execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            execution_request = TaskExecutionRequest(
                task_id=task_id,
                start_time=start_time,
                end_time=end_time,
                status=status,
                error_message=error_message,
                execution_time_ms=execution_time_ms
            )

            self.task_execution_dao.create(execution_request)
        except Exception as e:
            print(f"记录任务执行历史失败: {e}")

    def get_task_config(self, task_id: str) -> Optional[Dict]:
        """获取任务配置"""
        try:
            task_response = self.task_config_dao.get_one({"task_id": task_id})
            return task_response.dict() if task_response else None
        except Exception as e:
            print(f"获取任务配置失败: {e}")
            return None

    def get_all_task_configs(self) -> List[Dict]:
        """获取所有任务配置"""
        try:
            task_responses = self.task_config_dao.get_list({})
            return [task.dict() for task in task_responses]
        except Exception as e:
            print(f"获取所有任务配置失败: {e}")
            return []

    def upsert_task_config(self, task_id: str, task_name: str, description: str = "",
                           enabled: bool = False, interval_seconds: int = 60) -> bool:
        """插入或更新任务配置"""
        try:
            existing_task = self.task_config_dao.get_one({"task_id": task_id})

            if existing_task:
                # 更新现有任务
                update_request = TaskConfigRequest(
                    task_name=task_name,
                    description=description,
                    enabled=enabled,
                    interval_seconds=interval_seconds
                )
                self.task_config_dao.update({"task_id": task_id}, update_request)
            else:
                # 创建新任务
                create_request = TaskConfigRequest(
                    task_id=task_id,
                    task_name=task_name,
                    description=description,
                    enabled=enabled,
                    interval_seconds=interval_seconds
                )
                self.task_config_dao.create(create_request)

            return True
        except Exception as e:
            print(f"更新任务配置失败: {e}")
            return False

    def update_task_status(self, task_id: str, enabled: bool) -> bool:
        """更新任务启用状态"""
        try:
            update_request = TaskConfigRequest(enabled=enabled)
            result = self.task_config_dao.update({"task_id": task_id}, update_request)
            return result is not None
        except Exception as e:
            print(f"更新任务状态失败: {e}")
            return False

    def update_task_interval(self, task_id: str, interval_seconds: int) -> bool:
        """更新任务执行间隔"""
        try:
            update_request = TaskConfigRequest(interval_seconds=interval_seconds)
            result = self.task_config_dao.update({"task_id": task_id}, update_request)
            return result is not None
        except Exception as e:
            print(f"更新任务间隔失败: {e}")
            return False

    def log_task_execution(self, task_id: str, status: str, start_time: datetime,
                           end_time: datetime = None, error_message: str = None) -> bool:
        """记录任务执行历史"""
        try:
            self._log_execution(task_id, status, start_time, end_time, error_message)
            return True
        except Exception as e:
            print(f"记录任务执行失败: {e}")
            return False

    def update_task(self, task_id: str, enabled: bool = None, interval_seconds: int = None) -> Tuple[bool, str]:
        """更新任务配置"""
        try:
            # 检查任务是否存在
            config = self.get_task_config(task_id)
            if not config:
                return False, f"任务 {task_id} 不存在"

            # 更新数据库
            update_fields = {}
            if enabled is not None:
                update_fields['enabled'] = enabled
            if interval_seconds is not None:
                update_fields['interval_seconds'] = interval_seconds

            if update_fields:
                update_request = TaskConfigRequest(**update_fields)
                self.task_config_dao.update({"task_id": task_id}, update_request)

            # 重新获取配置
            updated_config = self.get_task_config(task_id)
            if not updated_config:
                return False, "获取更新后的配置失败"

            # 立即应用更改到调度器
            current_job = self.scheduler.get_job(task_id)

            if updated_config['enabled']:
                # 启用任务
                if current_job and interval_seconds is not None:
                    # 间隔有变化，重新创建任务
                    self.scheduler.remove_job(task_id)

                if not current_job or interval_seconds is not None:
                    self._add_job(task_id, updated_config['interval_seconds'])
            else:
                # 禁用任务
                if current_job:
                    self.scheduler.remove_job(task_id)
                    print(f"任务 {task_id} 已停止")

            return True, "任务配置已更新"

        except Exception as e:
            error_msg = f"更新任务失败: {e}"
            print(error_msg)
            return False, error_msg

    def get_task_status(self) -> Dict:
        """获取所有任务状态"""
        try:
            configs = self.get_all_task_configs()
            status = {}

            for config in configs:
                task_id = config['task_id']
                job = self.scheduler.get_job(task_id)

                status[task_id] = {
                    'config': config,
                    'running': job is not None,
                    'next_run': str(job.next_run_time) if job and job.next_run_time else None,
                    'registered': TaskRegistry.get_task(task_id) is not None
                }

            return status
        except Exception as e:
            print(f"获取任务状态失败: {e}")
            return {}

    def get_task_execution_history(self, task_id: str, limit: int = 10) -> List[Dict]:
        """获取任务执行历史"""
        try:
            # 使用分页查询获取执行历史
            execution_responses = self.task_execution_dao.get_list_page(
                {"task_id": task_id},
                page=1,
                page_size=limit,
                desc_order_column="start_time"
            )
            return [execution.dict() for execution in execution_responses.items]
        except Exception as e:
            print(f"获取任务执行历史失败: {e}")
            return []

    def get_all_execution_history(self, limit: int = 50) -> List[Dict]:
        """获取所有任务的执行历史"""
        try:
            execution_responses = self.task_execution_dao.get_list_page(
                {},
                page=1,
                page_size=limit,
                desc_order_column="start_time"
            )
            return [execution.dict() for execution in execution_responses.items]
        except Exception as e:
            print(f"获取执行历史失败: {e}")
            return []

    def delete_task_config(self, task_id: str) -> bool:
        """删除任务配置"""
        try:
            # 先停止任务
            if self.scheduler.get_job(task_id):
                self.scheduler.remove_job(task_id)

            # 删除数据库记录
            self.task_config_dao.delete({"task_id": task_id})
            print(f"任务 {task_id} 已删除")
            return True
        except Exception as e:
            print(f"删除任务失败: {e}")
            return False

    def clean_execution_history(self, task_id: str = None, days: int = 30) -> bool:
        """清理执行历史记录

        Args:
            task_id: 任务ID，如果为None则清理所有任务
            days: 保留最近多少天的记录
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)

            # 构建查询条件
            query_conditions = {"start_time": cutoff_date}  # 这里需要根据实际DAO实现调整
            if task_id:
                query_conditions["task_id"] = task_id

            # 注意：这里需要根据实际的DAO实现来进行批量删除
            # 由于BaseDao没有直接的批量删除方法，这里留作扩展点
            print(f"清理执行历史功能需要根据具体需求实现")
            return True
        except Exception as e:
            print(f"清理执行历史失败: {e}")
            return False


# 使用示例和测试
def example_usage():
    """使用示例"""

    # 1. 初始化数据库（如果需要）
    if not db.is_initialized:
        db.init_default_db("scheduler.db")
        db.create_all()

    # 2. 使用装饰器注册任务
    @task("example_task_1", "示例任务1", "这是第一个示例任务", default_interval=10, default_enabled=True)
    def example_task_1():
        print(f"[{datetime.now()}] 执行示例任务1")
        import time
        time.sleep(1)  # 模拟任务执行时间

    @task("example_task_2", "示例任务2", "这是第二个示例任务", default_interval=5, default_enabled=False)
    def example_task_2():
        print(f"[{datetime.now()}] 执行示例任务2")
        import time
        time.sleep(0.5)

    @task("error_task", "错误任务", "这是一个会出错的任务", default_interval=15, default_enabled=False)
    def error_task():
        print(f"[{datetime.now()}] 执行会出错的任务")
        raise Exception("这是一个模拟的错误")

    # 3. 创建和启动调度器
    scheduler_manager = SchedulerManager()
    scheduler_manager.start()

    # 4. 管理任务
    print("\n=== 初始任务状态 ===")
    status = scheduler_manager.get_task_status()
    for task_id, task_status in status.items():
        print(f"任务 {task_id}: 启用={task_status['config']['enabled']}, "
              f"运行中={task_status['running']}, "
              f"已注册={task_status['registered']}")

    # 启用第二个任务
    print("\n=== 启用示例任务2 ===")
    success, message = scheduler_manager.update_task("example_task_2", enabled=True)
    print(f"更新结果: {success}, {message}")

    # 启用错误任务（用于测试错误处理）
    print("\n=== 启用错误任务 ===")
    success, message = scheduler_manager.update_task("error_task", enabled=True)
    print(f"更新结果: {success}, {message}")

    # 等待一段时间让任务执行
    print("\n=== 等待任务执行 ===")
    import time
    time.sleep(20)

    # 查看执行历史
    print("\n=== 任务执行历史 ===")
    for task_id in ["example_task_1", "example_task_2", "error_task"]:
        history = scheduler_manager.get_task_execution_history(task_id, limit=3)
        print(f"\n{task_id} 执行历史:")
        for record in history:
            print(f"  - {record['start_time']}: {record['status']} "
                  f"({record.get('execution_time_ms', 'N/A')}ms)")
            if record.get('error_message'):
                print(f"    错误: {record['error_message']}")

    # 修改任务间隔
    print("\n=== 修改任务间隔 ===")
    success, message = scheduler_manager.update_task("example_task_1", interval_seconds=3)
    print(f"修改任务1间隔结果: {success}, {message}")

    # 再等待一段时间观察效果
    print("\n=== 观察间隔变化效果 ===")
    time.sleep(10)

    # 最终状态
    print("\n=== 最终任务状态 ===")
    status = scheduler_manager.get_task_status()
    for task_id, task_status in status.items():
        config = task_status['config']
        print(f"任务 {task_id}:")
        print(f"  - 名称: {config['task_name']}")
        print(f"  - 启用: {config['enabled']}")
        print(f"  - 间隔: {config['interval_seconds']}秒")
        print(f"  - 运行中: {task_status['running']}")
        print(f"  - 下次执行: {task_status['next_run']}")

    # 5. 关闭调度器
    print("\n=== 关闭调度器 ===")
    scheduler_manager.shutdown()


def test_task_registry():
    """测试任务注册功能"""
    print("=== 测试任务注册 ===")

    # 清空之前的注册
    TaskRegistry._tasks.clear()

    # 注册测试任务
    @task("test_task_1", "测试任务1", "用于测试的任务1")
    def test_func_1():
        return "test1 executed"

    @task("test_task_2", "测试任务2", "用于测试的任务2", default_interval=30, default_enabled=True)
    def test_func_2():
        return "test2 executed"

    # 验证注册结果
    all_tasks = TaskRegistry.get_all_tasks()
    print(f"注册的任务数量: {len(all_tasks)}")

    for task_id, task_info in all_tasks.items():
        print(f"任务 {task_id}:")
        print(f"  - 名称: {task_info['name']}")
        print(f"  - 描述: {task_info['description']}")
        print(f"  - 默认间隔: {task_info['default_interval']}秒")
        print(f"  - 默认启用: {task_info['default_enabled']}")

        # 测试函数调用
        func = TaskRegistry.get_task_function(task_id)
        if func:
            result = func()
            print(f"  - 执行结果: {result}")

    print("任务注册测试完成\n")


if __name__ == "__main__":
    # 运行测试
    test_task_registry()

    # 运行完整示例
    example_usage()