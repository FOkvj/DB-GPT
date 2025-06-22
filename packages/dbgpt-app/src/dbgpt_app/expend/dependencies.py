from dbgpt._private.config import Config
from dbgpt.component import ComponentType
from dbgpt_app.expend.service.file_manager import PipelineWebManager
from dbgpt_app.expend.service.file_scanner_v2 import FileScanner
from dbgpt_app.expend.service.scheduler_manager_v2 import SchedulerManager

from dbgpt_app.expend.service.speech2text import Speech2TextService
from voice2text.tran.funasr_transcriber import FunASRTranscriber

CFG = Config()
def get_scanner() -> FileScanner:
    """依赖注入：获取扫描器实例"""
    return CFG.SYSTEM_APP.get_component(ComponentType.FILE_SCANNER, FileScanner)

def get_scheduler_manager() -> SchedulerManager:
    """依赖注入：获取计划任务管理器实例"""
    return CFG.SYSTEM_APP.get_component(ComponentType.SCHEDULE_MANAGER, SchedulerManager)

def get_pipeline_manager() -> PipelineWebManager:
    """依赖注入：获取管道管理器实例"""
    return CFG.SYSTEM_APP.get_component(ComponentType.PIPELINE_MANAGER, PipelineWebManager)

def get_speech2text_service() -> FunASRTranscriber:
    """依赖注入：获取语音转文字服务实例"""
    return CFG.SYSTEM_APP.get_component(ComponentType.SPEECH_TO_TEXT, Speech2TextService).transcriber