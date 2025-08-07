import os

from dbgpt import SystemApp
from dbgpt_app.expend.dao.data_manager import SQLiteConfig, initialize_expend_db
from dbgpt_app.expend.decorators.schedule_decorator import task
from dbgpt_app.expend.model.file_process import FileBucket
from dbgpt_app.expend.service.file_scanner_v2 import FileScanner
from dbgpt_app.expend.service.pipeline_manager import PipelineManager
from dbgpt_app.expend.service.processor_manager import MessageQueueProcessorManager, AudioToTextProcessor, \
    KnowledgeProcessor
from dbgpt_app.expend.service.queue.mq import RabbitMQManager
from dbgpt_app.expend.service.scheduler_manager_v2 import SchedulerManager
from dbgpt_app.expend.service.speech2text import Speech2TextService




def init_expend_modules(system_app: SystemApp):

    sqlite_config = SQLiteConfig(sqlite_path="test_expend.db", echo=True)
    print(f"SQLite配置: {sqlite_config.model_dump()}")
    print(f"数据库URL: {sqlite_config.get_database_url()}")
    print(f"引擎参数: {sqlite_config.get_engine_args()}")

    # 初始化数据库
    init_db = initialize_expend_db(sqlite_config)

    file_scanner = FileScanner()

    scheduler_manager = SchedulerManager()
    mq_manager = RabbitMQManager()
    processor_manager = MessageQueueProcessorManager(mq_manager)
    speech2text_service = Speech2TextService(server_url="http://localhost:8765")

    audio_processor = AudioToTextProcessor(
        transcriber=speech2text_service,
        mq_manager=mq_manager,
        config={'output_bucket': FileBucket.TO_KONWLEDGE}
    )
    processor_manager.register_processor(audio_processor)

    # 注册知识库处理器
    knowledge_processor = KnowledgeProcessor(
        mq_manager=mq_manager,
        config={'enable_summary': True}
    )
    processor_manager.register_processor(knowledge_processor)

    system_app.register_instance(scheduler_manager)
    system_app.register_instance(mq_manager)
    system_app.register_instance(processor_manager)
    system_app.register_instance(file_scanner)
    system_app.register_instance(speech2text_service)
    pipeline_manager = PipelineManager()
    system_app.register_instance(pipeline_manager)

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
        # # 添加本地目录
        # file_scanner.add_local_directory("测试目录1",
        #                                  "/Users/dzc/Desktop/dbgpt_PR/DB-GPT/packages/dbgpt-app/src/dbgpt_app/expend/test")
        #
        # # 添加FTP服务器
        # file_scanner.add_ftp_server("FTP服务器1", "localhost", "t10", "1234", remote_dir="/")
        file_scanner.scan_and_sync()
    scheduler_manager.start()


