from dbgpt_app.expend.model.file_process import ProcessTopic


def get_topic_by_file_type(file_type: str) -> str:
    """
    根据文件类型决定消息队列主题

    Args:
        file_type: 文件扩展名（如 .mp3, .txt）

    Returns:
        str: 消息队列主题名称 ('stt' 或 'to_knowledge')
    """
    # 音频文件类型 - 发送到 stt 主题
    audio_extensions = {
        '.mp3', '.wav', '.flac', '.aac', '.ogg',
        '.m4a', '.wma', '.opus', '.aiff', '.au'
    }

    # 文本文档类型 - 发送到 to_knowledge 主题
    text_extensions = {
        '.txt', '.csv', '.doc', '.docx', '.pdf',
        '.xlsx', '.xls', '.ppt', '.pptx', '.rtf',
        '.md', '.json', '.xml', '.html', '.htm',
        '.py', '.java', '.cpp', '.c', '.js', '.ts'
    }

    file_ext = file_type.lower().strip()

    if file_ext in audio_extensions:
        return ProcessTopic.STT.value
    elif file_ext in text_extensions:
        return ProcessTopic.TO_KNOWLEDGE.value
    else:
        # 默认情况下，未知文件类型发送到 to_knowledge
        return 'to_knowledge'