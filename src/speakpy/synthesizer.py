from .config import APP_NAME, MODEL_FILENAME 

from pedalboard import Bitcrush, Distortion, HighpassFilter, PeakFilter, Chorus, Reverb, Delay, Compressor, Limiter 
from pedalboard._pedalboard import Pedalboard
from piper import AudioChunk, PiperVoice, SynthesisConfig
from huggingface_hub import hf_hub_download
from platformdirs import user_data_dir
import sounddevice as sd
import numpy as np
import os

from typing import Iterable

class Synthesizer:
    def __init__(self):
        model_dir = os.path.join(user_data_dir(APP_NAME), "models")
        os.makedirs(model_dir, exist_ok=True)
        for fn in [MODEL_FILENAME, MODEL_FILENAME + ".json"]:
            path = os.path.join(model_dir, fn)
            if not os.path.exists(path):
                hf_hub_download(
                    repo_id="rhasspy/piper-voices",
                    filename=fn,
                    local_dir=model_dir
                )
        self._syn_config = SynthesisConfig(
            noise_scale=1.0,  
            noise_w_scale=0.1,  
        )
        self._voice = PiperVoice.load(os.path.join(model_dir, MODEL_FILENAME))

    def get_sample_rate(self) -> int:
        return self._voice.config.sample_rate

    def synthesize(self, text: str, speed: float) -> Iterable[AudioChunk]:
        assert speed > 0.0, "Expected speed above 0.0" 
        syn_config = self._syn_config
        syn_config.length_scale = speed 
        yield from self._voice.synthesize(text, syn_config)
        
    def speak(self, text: str, speed: float):
        assert speed > 0.0, "Expected speed above 0.0" 
        syn_config = self._syn_config
        syn_config.length_scale = speed 
        try:
            sample_rate = self._voice.config.sample_rate
            with sd.RawOutputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
                last_chunk = None

                for chunk in self._voice.synthesize(text, syn_config=self._syn_config):
                    last_chunk = chunk

        except sd.PortAudioError:
            return
