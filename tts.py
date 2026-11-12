"""Voice output that can be interrupted mid-sentence.

Text is first turned into audio (Piper neural voice, or the built-in Windows voice),
then played with sounddevice in a loop that checks 'should_stop' many times a second.
"""
import os
import tempfile
import time
import wave

import numpy as np
import sounddevice as sd

import config


class Speaker:
    def __init__(self):
        self.backend = None
        self.engine = None
        self.piper = None
        mode = config.TTS_ENGINE

        if mode in ("auto", "piper"):
            try:
                self._init_piper()
                self.backend = "piper"
            except Exception as e:
                if mode == "piper":
                    print(f"[!] Piper voice not available ({e}). Falling back to the Windows voice.")
                else:
                    print("(Using the Windows voice. For a much better voice, run get_voice.bat)")

        if self.backend is None:
            self._init_windows()
            self.backend = "windows"

    # ----- Piper -------------------------------------------------------------
    def _init_piper(self):
        if not os.path.exists(config.PIPER_VOICE):
            raise FileNotFoundError(config.PIPER_VOICE)
        from piper import PiperVoice

        self.piper = PiperVoice.load(config.PIPER_VOICE)
        self.piper_rate = self.piper.config.sample_rate
        self.syn_config = None
        try:
            from piper import SynthesisConfig

            self.syn_config = SynthesisConfig(length_scale=config.PIPER_LENGTH_SCALE)
        except Exception:
            pass
        list(self.piper.synthesize("Ready."))  # warm-up

    def _synth_piper(self, text):
        kwargs = {"syn_config": self.syn_config} if self.syn_config else {}
        chunks = [c.audio_int16_array for c in self.piper.synthesize(text, **kwargs)]
        if not chunks:
            return None, self.piper_rate
        return np.concatenate(chunks), self.piper_rate

    # ----- Windows built-in voice -------------------------------------------
    def _init_windows(self):
        import pyttsx3

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", config.SPEECH_RATE)
        hint = config.VOICE_HINT.lower()
        for voice in self.engine.getProperty("voices"):
            if hint in voice.name.lower():
                self.engine.setProperty("voice", voice.id)
                break

    def _synth_windows(self, text):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            self.engine.save_to_file(text, path)
            self.engine.runAndWait()
            with wave.open(path, "rb") as w:
                rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
                raw = w.readframes(w.getnframes())
            if width != 2 or not raw:
                return None, rate
            audio = np.frombuffer(raw, dtype=np.int16)
            if channels > 1:
                audio = audio.reshape(-1, channels)
            return audio, rate
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # ----- public ------------------------------------------------------------
    def synth(self, text):
        if self.backend == "piper":
            return self._synth_piper(text)
        return self._synth_windows(text)

    def speak(self, text, should_stop) -> bool:
        """Speak one chunk of text. Returns True if she was interrupted."""
        try:
            audio, rate = self.synth(text)
        except Exception as e:
            print(f"[!] voice error: {e}")
            audio, rate = None, 0

        if audio is None or len(audio) == 0:
            # last resort: blocking Windows speech that cannot be interrupted
            if self.engine is not None:
                self.engine.say(text)
                self.engine.runAndWait()
            return False

        if should_stop():
            return True
        sd.play(audio, rate)
        end = time.time() + len(audio) / rate + 0.3
        while time.time() < end:
            if should_stop():
                sd.stop()
                return True
            time.sleep(0.02)
        sd.wait()
        return False

    def chime(self):
        """Short two-note beep that says 'I heard you'."""
        rate = 22050
        t = np.linspace(0, 0.09, int(rate * 0.09), endpoint=False)
        tone = np.concatenate([np.sin(2 * np.pi * f * t) for f in (660, 880)])
        tone = (tone * 0.25 * 32767).astype(np.int16)
        try:
            sd.play(tone, rate)
            sd.wait()
        except Exception:
            pass
