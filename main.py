"""FRIDAY - local voice assistant.  Start with:  python main.py  (or double-click run.bat)

mic -> speech detection -> Faster-Whisper -> PC commands or Ollama LLM
    -> sentence-by-sentence speech (interruptible) while the LLM is still writing.
"""
import datetime
import queue
import random
import re
import threading
import time

import config
import llm
import tools
from asr import ASR
from audio_in import BargeMonitor, Mic
from memory import Memory
from tts import Speaker

JUNK = {"", "you", "thank you", "thanks", "bye", "thanks for watching", "okay", "uh", "um", "hmm"}


class Friday:
    def __init__(self):
        print(f"\n=== {config.ASSISTANT_NAME.upper()} starting up ===")
        print("Loading speech recognition (first run downloads ~150 MB)...")
        self.asr = ASR()
        self.memory = Memory()
        print("Loading voice...")
        self.speaker = Speaker()
        print(f"   voice engine: {self.speaker.backend}")
        print("Waking up the language model...")
        try:
            llm.warm_up()
        except Exception as e:
            print(f"\n[!] Cannot reach Ollama / model '{config.LLM_MODEL}': {e}")
            print("    Open the Ollama app, then run:  ollama pull " + config.LLM_MODEL)
            raise SystemExit(1)
        self.mic = Mic()
        print("Calibrating microphone - stay quiet for a second...")
        self.mic.start()

        self.barge = BargeMonitor(self.mic) if config.BARGE_IN else None
        self.key_stop = threading.Event()
        self.speaking = False
        self.carry = None           
        self.active_until = 0.0     
        self.sleeping = False
        if config.STOP_KEY:
            threading.Thread(target=self._key_listener, daemon=True).start()


    def _key_listener(self):
        try:
            import msvcrt
        except ImportError:
            return
        while True:
            try:
                if msvcrt.kbhit():
                    msvcrt.getwch()
                    if self.speaking:
                        self.key_stop.set()
                else:
                    time.sleep(0.05)
            except Exception:
                return

   
    def should_stop(self) -> bool:
        if self.key_stop.is_set():
            return True
        return bool(self.barge and self.barge.update())

    def begin_speaking(self):
        self.speaking = True
        self.key_stop.clear()
        if self.barge:
            self.mic.flush()
            self.barge.reset()
        else:
            self.mic.muted = True

    def end_speaking(self):
        self.speaking = False
        if self.barge:
            if self.barge.triggered:
                self.carry = self.barge.carry()     
            else:
                self.mic.flush()
        else:
            time.sleep(0.3)
            self.mic.flush()
            self.mic.muted = False

    def say(self, text: str):
        """Speak a finished piece of text, sentence by sentence, interruptible."""
        chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        self.begin_speaking()
        try:
            for s in chunks:
                print(f"{config.ASSISTANT_NAME}: {s}")
                if self.speaker.speak(s, self.should_stop):
                    break
        finally:
            self.end_speaking()

    def chime(self):
        self.begin_speaking()
        try:
            self.speaker.chime()
        finally:
            self.end_speaking()

    def greeting(self) -> str:
        h = datetime.datetime.now().hour
        part = "morning" if h < 12 else "afternoon" if h < 17 else "evening"
        t = config.USER_TITLE
        return random.choice([
            f"Good {part}, {t}. All systems are online and standing by.",
            f"Good {part}, {t}. {config.ASSISTANT_NAME} is online. How may I be of service?",
            f"Welcome back, {t}. All systems nominal.",
        ])

    def system_prompt(self) -> str:
        now = datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
        prompt = config.system_prompt() + f"\nCurrent date and time: {now}."
        if self.memory.notes:
            prompt += "\nThings the user asked you to remember:\n"
            prompt += "\n".join(f"- {n}" for n in self.memory.notes)
        return prompt

   
    def llm_turn(self, text: str, t_end: float, t_asr: float):
        messages = [
            {"role": "system", "content": self.system_prompt()},
            *self.memory.history,
            {"role": "user", "content": text},
        ]
        sentences: queue.Queue = queue.Queue()
        cancel = threading.Event()
        parts: list = []
        info: dict = {}

        def produce():
            buf = ""
            try:
                for tok in llm.stream_reply(messages):
                    if cancel.is_set():
                        break
                    info.setdefault("first_token", time.perf_counter())
                    parts.append(tok)
                    buf += tok
                    done, buf = llm.sentence_chunks(buf)
                    for s in done:
                        sentences.put(s)
                if buf.strip() and not cancel.is_set():
                    sentences.put(buf.strip())
            except Exception as e:  
                info["error"] = e
            finally:
                sentences.put(None)

        threading.Thread(target=produce, daemon=True).start()

        spoken: list = []
        interrupted = False
        filler_said = not config.THINKING_FILLER
        t_wait = time.perf_counter()
        self.begin_speaking()
        try:
            while True:
                try:
                    sentence = sentences.get(timeout=0.05)
                except queue.Empty:
                   
                    if not interrupted and self.should_stop():
                        interrupted = True
                        cancel.set()
                   
                    elif (not filler_said and not interrupted and "first_token" not in info
                          and time.perf_counter() - t_wait > config.THINKING_DELAY_S):
                        filler_said = True
                        phrase = config.thinking_phrase()
                        print(f"{config.ASSISTANT_NAME}: {phrase}")
                        if self.speaker.speak(phrase, self.should_stop):
                            interrupted = True
                            cancel.set()
                    continue
                if sentence is None:
                    break
                if interrupted:
                    continue
                info.setdefault("speaking", time.perf_counter())
                print(f"{config.ASSISTANT_NAME}: {sentence}")
                if self.speaker.speak(sentence, self.should_stop):
                    interrupted = True
                    cancel.set()
                else:
                    spoken.append(sentence)
        finally:
            self.end_speaking()

        if interrupted:
            print("   (interrupted)")

        if "error" in info and not spoken:
            print(f"[!] LLM error: {info['error']}")
            self.say(f"I can't reach my language model, {config.USER_TITLE}. Is Ollama running?")
            return

        reply = " ".join(spoken) if interrupted else "".join(parts).strip()
        if reply:
            self.memory.add_turn(text, reply)

        if "speaking" in info:
            print(
                "   latency: "
                f"speech-to-text {int((t_asr - t_end) * 1000)} ms | "
                f"first LLM token +{int((info.get('first_token', t_asr) - t_asr) * 1000)} ms | "
                f"started speaking {int((info['speaking'] - t_end) * 1000)} ms after you stopped"
            )

    def run(self):
        self.say(self.greeting())
        if config.WAKE_REQUIRED:
            print(f"(Wake word is ON - start with {' or '.join(config.WAKE_NAMES)}. "
                  f"After that you can keep talking for {config.CONVERSATION_WINDOW_S} s.)")
        if config.BARGE_IN:
            print("(Interrupt: just talk over her, or press any key. Use headphones.)")
        try:
            while True:
                print("\n[listening...]" + ("  (asleep - say my name to wake me)" if self.sleeping else ""))
                audio = self.mic.listen(initial=self.carry, idle_cb=tools.has_due)
                self.carry = None

                if audio is None:                      
                    for message in tools.pop_due():
                        self.say(message)
                    continue

                t_end = time.perf_counter()
                text = self.asr.transcribe(audio)
                t_asr = time.perf_counter()

                norm = tools.normalize(text)
                if norm in JUNK:
                    continue
                print(f"You: {text}")

                heard_wake, cmd = tools.strip_wake(norm)
                if self.sleeping:
                    if not heard_wake:
                        print("(asleep - ignored)")
                        continue
                    self.sleeping = False
                elif config.WAKE_REQUIRED and not heard_wake and time.time() > self.active_until:
                    print(f"(ignored - say {' or '.join(config.WAKE_NAMES)} first)")
                    continue

                self.active_until = time.time() + config.CONVERSATION_WINDOW_S

                if not cmd:                             
                    if config.WAKE_CHIME:
                        self.chime()
                    self.say(f"Yes, {config.USER_TITLE}?")
                    continue

                result = tools.handle(cmd, self.memory)
                if result is not None:
                    reply, action = result
                    if reply:
                        self.say(reply)
                    if action == "exit":
                        break
                    if action == "sleep":
                        self.sleeping = True
                    self.active_until = time.time() + config.CONVERSATION_WINDOW_S
                    continue

                self.llm_turn(cmd if heard_wake else text, t_end, t_asr)
                self.active_until = time.time() + config.CONVERSATION_WINDOW_S
        except KeyboardInterrupt:
            print("\nShutting down.")
        finally:
            self.mic.close()


if __name__ == "__main__":
    Friday().run()
