import logging
import os

from dbgpt import BaseComponent
from dbgpt.component import ComponentType, SystemApp
from voice2text.tran.funasr_transcriber import FunASRTranscriber

logger = logging.getLogger(__name__)

class Speech2TextService(BaseComponent):
    name = ComponentType.SPEECH_TO_TEXT

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._transcriber = None
    def init_app(self, system_app: SystemApp):
        pass

    @property
    def transcriber(self) -> FunASRTranscriber:
        if self._transcriber is None:
            self.init()
        return self._transcriber


    def init(self):
        logger.info("Init Speech2TextService")
        self._transcriber = FunASRTranscriber(
            device="cpu",
            voice_prints_path=os.path.join(os.path.expanduser("~"), ".cache"),
            max_voiceprint_length=30,  # 限制声纹最大长度为30秒
            # funasr_model="iic/SenseVoiceSmall",
            funasr_model="paraformer-zh",
            funasr_model_revision="v2.0.4",
            vad_model="fsmn-vad",
            vad_model_revision="v2.0.4",
            punc_model="ct-punc",
            punc_model_revision="v2.0.4",
            spk_model="cam++",
            spk_model_revision="v2.0.2"
        )

    def list_registered_voices(self, include_unnamed=True):
        return self.transcriber.list_registered_voices(include_unnamed)

    def get_voiceprint_sample_paths(self, voiceprint_id=None):
        return self.transcriber.voice_print_manager.get_voiceprint_sample_paths(voiceprint_id)

    def get_sample_path_by_id(self, sample_id):
        return self.transcriber.voice_print_manager.get_sample_path_by_id(sample_id)

    def register_voice(self, voice_name, audio_file_path):
        return self.transcriber.register_voice(voice_name, audio_file_path)
    def voice_prints_dir(self):
        return self.transcriber.voice_print_manager.voice_prints_dir

    def rename_voice_print(self, voice_id, new_name):
        return self.transcriber.rename_voice_print(voice_id, new_name)



    def transcribe_file(self, audio_file_path,
                        batch_size_s=300,
                        hotword='',
                        threshold=0.4,
                        auto_register_unknown=True,
                        file_location=None,
                        file_date=None,
                        file_time=None):

        return self.transcriber.transcribe_file(
            audio_file_path,
            batch_size_s=batch_size_s,
            hotword=hotword,
            threshold=threshold,
            auto_register_unknown=auto_register_unknown,
            file_location=file_location,
            file_date=file_date,
            file_time=file_time
        )

