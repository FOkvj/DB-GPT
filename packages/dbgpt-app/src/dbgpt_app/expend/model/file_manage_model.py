from enum import Enum


class AudioFileType(str, Enum):
    """音频文件类型枚举"""
    # 无损音频格式
    WAV = ".wav"
    FLAC = ".flac"
    AIFF = ".aiff"
    AU = ".au"
    APE = ".ape"

    # 有损音频格式
    MP3 = ".mp3"
    AAC = ".aac"
    M4A = ".m4a"
    OGG = ".ogg"
    WMA = ".wma"
    OPUS = ".opus"

    # 其他音频格式
    AMR = ".amr"
    CAF = ".caf"
    DSD = ".dsd"
    MKA = ".mka"
    RA = ".ra"
    AC3 = ".ac3"
    DTS = ".dts"
