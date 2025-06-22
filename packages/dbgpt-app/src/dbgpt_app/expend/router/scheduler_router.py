from flask import request, jsonify
from fastapi import APIRouter, HTTPException, Depends, Body

from dbgpt.core.schema.api import Result
from dbgpt_app.expend.dependencies import get_scheduler_manager
from dbgpt_app.expend.service.scheduler_manager_v2 import SchedulerManager

router = APIRouter()


@router.get('/tasks')
def get_tasks(scheduler_manager: SchedulerManager = Depends(get_scheduler_manager)):
    """获取所有任务状态"""
    try:
        status = scheduler_manager.get_task_status()
        return Result.succ(status)
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.get('/tasks/{task_id}')
def get_task(task_id: str, scheduler_manager: SchedulerManager = Depends(get_scheduler_manager)):
    """获取单个任务详情"""
    try:
        config = scheduler_manager.get_task_config(task_id)
        if not config:
            return Result.failed(f'任务 {task_id} 不存在', "E404")

        job = scheduler_manager.scheduler.get_job(task_id)
        return Result.succ({
            'config': dict(config),
            'running': job is not None,
            'next_run': str(job.next_run_time) if job and job.next_run_time else None
        })
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.put('/tasks/{task_id}')
def update_task(task_id: str, data: dict = Body(...), scheduler_manager: SchedulerManager = Depends(get_scheduler_manager)):
    """更新任务配置"""
    try:
        if not data:
            return Result.failed('请提供JSON数据', "E400")

        enabled = data.get('enabled')
        interval_seconds = data.get('interval_seconds')
        if enabled is None or interval_seconds is None:
            return Result.failed('enabled和interval_seconds不可为None', "E400")

        if interval_seconds is not None:
            if not isinstance(interval_seconds, int) or interval_seconds <= 0:
                return Result.failed('时间间隔必须是正整数', "E400")

        success, message = scheduler_manager.update_task(task_id, enabled, interval_seconds)

        if success:
            return Result.succ(message)
        else:
            return Result.failed(message, "E400")
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.post('/tasks/{task_id}/start')
def start_task(task_id: str, scheduler_manager: SchedulerManager = Depends(get_scheduler_manager)):
    """启动任务"""
    try:
        success, message = scheduler_manager.update_task(task_id, enabled=True)
        if success:
            return Result.succ(message)
        else:
            return Result.failed(message, "E400")
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.post('/tasks/{task_id}/stop')
def stop_task(task_id: str, scheduler_manager: SchedulerManager = Depends(get_scheduler_manager)):
    """停止任务"""
    try:
        success, message = scheduler_manager.update_task(task_id, enabled=False)
        if success:
            return Result.succ(message)
        else:
            return Result.failed(message, "E400")
    except Exception as e:
        return Result.failed(str(e), "E500")

@router.get('/tasks/{task_id}/executions')
def get_task_executions(task_id: str, scheduler_manager: SchedulerManager = Depends(get_scheduler_manager)):
    """获取任务执行历史"""
    try:
        limit = request.args.get('limit', 50, type=int)

        with scheduler_manager.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM task_executions 
                WHERE task_id = ? 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (task_id, limit))
            executions = [dict(row) for row in cursor.fetchall()]

        return Result.succ(executions)
    except Exception as e:
        return Result.failed(str(e), "E500")