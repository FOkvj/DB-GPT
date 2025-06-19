from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from dbgpt import BaseComponent
from dbgpt.component import ComponentType, SystemApp
from dbgpt_app.expend.dao.schedule_dao import ScheduleDatabaseManager
from dbgpt_app.expend.decorators.schedule_decorator import TaskRegistry


class SchedulerManager(BaseComponent):
    name = ComponentType.SCHEDULE_MANAGER

    def __init__(self, db_path: str = 'scheduler.db'):
        self.scheduler = BackgroundScheduler()
        self.db = ScheduleDatabaseManager(db_path)

    def init_app(self, system_app: SystemApp):
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
            self.db.upsert_task_config(
                task_id=task_id,
                task_name=task_info['name'],
                description=task_info['description'],
                enabled=task_info['default_enabled'],
                interval_seconds=task_info['default_interval']
            )

    def _load_and_start_tasks(self):
        """从数据库加载并启动启用的任务"""
        configs = self.db.get_all_task_configs()
        for config in configs:
            if config['enabled']:
                self._add_job(config['task_id'], config['interval_seconds'])

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
                    self.db.log_task_execution(task_id, 'success', start_time, end_time)
                except Exception as e:
                    end_time = datetime.now()
                    error_msg = str(e)
                    print(f"任务 {task_id} 执行失败: {error_msg}")
                    self.db.log_task_execution(task_id, 'failed', start_time, end_time, error_msg)

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

    def update_task(self, task_id: str, enabled: bool = None, interval_seconds: int = None) -> tuple:
        """更新任务配置"""
        config = self.db.get_task_config(task_id)
        if not config:
            return False, f"任务 {task_id} 不存在"

        # 更新数据库
        if enabled is not None:
            self.db.update_task_status(task_id, enabled)
        if interval_seconds is not None:
            self.db.update_task_interval(task_id, interval_seconds)

        # 重新加载配置
        updated_config = self.db.get_task_config(task_id)

        # 立即应用更改
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

    def get_task_status(self) -> dict:
        """获取所有任务状态"""
        configs = self.db.get_all_task_configs()
        status = {}

        for config in configs:
            task_id = config['task_id']
            job = self.scheduler.get_job(task_id)

            status[task_id] = {
                'config': dict(config),
                'running': job is not None,
                'next_run': str(job.next_run_time) if job and job.next_run_time else None,
                'registered': TaskRegistry.get_task(task_id) is not None
            }

        return status