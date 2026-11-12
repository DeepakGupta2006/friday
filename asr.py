"""Speech to text with Faster-Whisper (INT8, CPU)."""
import numpy as np
from faster_whisper import WhisperModel

import config


class ASR:
    def __init__(self):
        self.model = WhisperModel(
            config.WHISPER_MODEL,
            device="cpu",
            compute_type=config.WHISPER_COMPUTE,
            cpu_threads=config.WHISPER_THREADS,
        )
        # warm-up: the generator must be consumed or nothing actually runs
        segments, _ = self.model.transcribe(np.zeros(16000, dtype=np.float32), beam_size=1)
        list(segments)

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,                      # greedy decoding = fastest
            vad_filter=True,                  # drops non-speech, avoids ghost text
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
            without_timestamps=True,
            initial_prompt=(", ".join(config.WAKE_NAMES)
                            + ", hey Jarvis, hey Friday, open Chrome, close Notepad, what time is it."),
        )
        return " ".join(s.text.strip() for s in segments).strip()
