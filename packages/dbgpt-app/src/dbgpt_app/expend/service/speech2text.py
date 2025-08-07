import logging
from typing import List

from voice2text.tran.client import VoiceSDKClient
from voice2text.tran.schema.dto import VoicePrintInfo
from voice2text.tran.schema.prints import SampleInfo
from voice2text.tran.server import ApiResponse

from dbgpt import BaseComponent
from dbgpt.component import ComponentType, SystemApp

logger = logging.getLogger(__name__)

class Speech2TextService(BaseComponent):
    name = ComponentType.SPEECH_TO_TEXT

    def __init__(self, server_url="http://localhost:8765", **kwargs):
        super().__init__(**kwargs)
        self._transcriber = None
        self.server_url = server_url
    def init_app(self, system_app: SystemApp):
        pass


    async def list_registered_voices(self, include_unnamed=True) -> ApiResponse[List[VoicePrintInfo]]:
        async with VoiceSDKClient(self.server_url) as client:
            return await client.list_voiceprints(include_unnamed)
    
    async def download_file(self, file_id: str, file_path: str) -> ApiResponse[None]:
        async with VoiceSDKClient(self.server_url) as client:
            return await client.download_file(file_id=file_id, local_path=file_path)

    async def delete_speaker(self, speaker_id: str) -> ApiResponse[None]:
        async with VoiceSDKClient(self.server_url) as client:
            return await client.delete_speaker(speaker_id)

    async def delete_audio_sample(self, speaker_id: str, audio_file_id: str) -> ApiResponse[None]:
        async with VoiceSDKClient(self.server_url) as client:
            return await client.delete_speaker_audio_sample(speaker_id, audio_file_id)

    async def get_file_stream(self, file_id: str):
        async with VoiceSDKClient(self.server_url, timeout=6000) as client:
            return await client.get_file_stream(file_id)

    async def register_voice(self, voice_name, audio_file_path) -> ApiResponse[SampleInfo]:
        async with VoiceSDKClient(self.server_url) as client:
            return await client.register_voiceprint_direct(voice_name, audio_file_path)


    async def rename_voice_print(self, voice_id, new_name):
        async with VoiceSDKClient(self.server_url) as client:
            return await client.rename_speaker(voice_id, new_name)



    async def transcribe_file(self, audio_file_path,
                              language="auto",
                        batch_size_s=300,
                        hotword='',
                        threshold=0.4,
                        auto_register_unknown=True,
                        file_location=None,
                        file_date=None,
                        file_time=None):
        async with VoiceSDKClient(self.server_url) as client:
            return await client.transcribe_file_direct(file_path=audio_file_path,
                                                       batch_size_s=batch_size_s,
                                                       threshold=threshold, timeout=60000,
                                                       language=language)

        # return self.transcriber.transcribe_file(
        #     audio_file_path,
        #     batch_size_s=batch_size_s,
        #     hotword=hotword,
        #     threshold=threshold,
        #     auto_register_unknown=auto_register_unknown,
        #     file_location=file_location,
        #     file_date=file_date,
        #     file_time=file_time,
        # )

