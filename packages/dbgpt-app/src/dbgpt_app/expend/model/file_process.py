from enum import Enum


class FileBucket(Enum):
    SCANNED = "scanned"
    TO_KONWLEDGE = "to_knowledge"


class ProcessTopic(Enum):
    """管道主题"""
    TO_KNOWLEDGE = "to_knowledge"
    STT = "stt"