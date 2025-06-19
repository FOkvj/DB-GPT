import uvicorn
from fastapi import FastAPI

from dbgpt import SystemApp
from dbgpt_app.expend.decorators.schedule_decorator import task
from dbgpt_app.expend.router.file_manager_router import router as file_manager_router
from dbgpt_app.expend.router.file_scan_config_router import router as file_scan_router
from dbgpt_app.expend.router.scheduler_router import router as scheduler_router
from dbgpt_app.expend.service.file_manager import PipelineWebManager
from dbgpt_app.expend.service.file_scanner import FileScanner
from dbgpt_app.expend.service.scheduler_manager import SchedulerManager
from dbgpt_app.expend.service.speech2text import Speech2TextService




def init_expend_modules(system_app: SystemApp):
    file_scanner = FileScanner()
    scheduler_manager = SchedulerManager()
    speech2text_service = Speech2TextService()
    speech2text_service.init()

    system_app.register_instance(scheduler_manager)
    system_app.register_instance(file_scanner)
    system_app.register_instance(speech2text_service)
    pipeline_manager = PipelineWebManager(["./service/input", "./service/output/transcripts"])
    system_app.register_instance(pipeline_manager)

    scheduler_manager.start()
    @task(
        task_id='file_scan',
        name='文件扫描任务',
        description='定时扫描远程ftp服务目录是否有新增文件',
        default_interval=5,
        default_enabled=True
    )
    def schedule_scan_task():
        # 设置文件大小限制为50MB
        file_scanner.set_max_file_size(50)
        # 添加本地目录
        # file_scanner.add_local_directory("测试目录1",
        #                                  "/Users/dzc/Desktop/dbgpt_PR/DB-GPT/packages/dbgpt-app/src/dbgpt_app/expend/test")

        # 添加FTP服务器
        file_scanner.add_ftp_server("FTP服务器1", "localhost", "t10", "1234", remote_dir="/")
        file_scanner.scan_and_sync()

