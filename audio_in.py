"""Microphone input: speech detection, plus a barge-in monitor used while Friday talks."""
import collections
import contextlib
import queue
import time

import numpy as np
import sounddevice as sd

import config


class Mic:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.muted = False
        self.noise = 50.0
        self.blocksize = config.SAMPLE_RATE * config.FRAME_MS // 1000
        self.stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=self.blocksize,
            device=config.MIC_DEVICE,
            callback=self._callback,
        )

    def _callback(self, indata, frames, time_info, status):
        if not self.muted:
            self.q.put(indata[:, 0].copy())

    @staticmethod
    def _rms(frame) -> float:
        return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

    def speech_threshold(self) -> float:
        return max(config.MIN_RMS, self.noise * config.SPEECH_MULT)

    def start(self):
        self.stream.start()
        # measure room noise for ~1 second (stay quiet)
        levels = []
        end = time.time() + 1.0
        while time.time() < end:
            try:
                levels.append(self._rms(self.q.get(timeout=0.5)))
            except queue.Empty:
                pass
        if levels:
            self.noise = max(float(np.mean(levels)), 10.0)

    def read_frame(self):
        """One waiting frame, or None. Never blocks."""
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None

    def flush(self):
        while self.read_frame() is not None:
            pass

    @contextlib.contextmanager
    def pause(self):
        """Mute the mic while Friday talks (used when barge-in is off)."""
        self.muted = True
        try:
            yield
        finally:
            time.sleep(0.3)
            self.flush()
            self.muted = False

    def listen(self, initial=None, idle_cb=None):
        """Block until one full utterance is heard. Returns float32 audio at 16 kHz.

        initial: frames already captured (from a barge-in) that start the utterance.
        idle_cb: called while waiting in silence. If it returns True, listen returns None
                 so the caller can handle something (like a timer going off).
        """
        frame_ms = config.FRAME_MS
        silence_needed = config.SILENCE_MS // frame_ms
        preroll = collections.deque(maxlen=8)  # keeps the start of the first word
        utt: list = []
        speaking = False
        hot = 0
        silent = 0

        if initial:
            speaking = True
            utt = list(initial)

        while True:
            try:
                frame = self.q.get(timeout=0.3)
            except queue.Empty:
                if not speaking and idle_cb and idle_cb():
                    return None
                continue

            rms = self._rms(frame)
            threshold = self.speech_threshold()

            if not speaking:
                preroll.append(frame)
                if rms > threshold:
                    hot += 1
                    if hot >= 3:
                        speaking = True
                        utt = list(preroll)
                        silent = 0
                else:
                    hot = 0
                    self.noise = 0.95 * self.noise + 0.05 * rms  # slowly track room noise
                    if idle_cb and idle_cb():
                        return None
                continue

            utt.append(frame)
            silent = 0 if rms > threshold else silent + 1
            too_long = len(utt) * frame_ms > config.MAX_UTTERANCE_S * 1000
            if silent >= silence_needed or too_long:
                speech_ms = (len(utt) - silent) * frame_ms
                if speech_ms >= config.MIN_SPEECH_MS:
                    return np.concatenate(utt).astype(np.float32) / 32768.0
                speaking, utt, hot = False, [], 0
                preroll.clear()

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


class BargeMonitor:
    """Watches the mic while Friday talks. update() returns True when you start talking."""

    def __init__(self, mic: Mic):
        self.mic = mic
        self.need = max(3, config.BARGE_MS // config.FRAME_MS)
        self.reset()

    def reset(self):
        self.recent = collections.deque(maxlen=18)   # ~0.5 s kept for the next utterance
        self.loud = 0
        self.triggered = False

    def update(self) -> bool:
        if self.triggered:
            return True
        threshold = max(config.BARGE_RMS, self.mic.noise * config.SPEECH_MULT * 2)
        while True:
            frame = self.mic.read_frame()
            if frame is None:
                return False
            self.recent.append(frame)
            if Mic._rms(frame) > threshold:
                self.loud += 1
            else:
                self.loud = max(0, self.loud - 1)
            if self.loud >= self.need:
                self.triggered = True
                return True

    def carry(self):
        return list(self.recent)
