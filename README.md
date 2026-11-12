# Friday: Local AI Voice Assistant

Friday is a private, voice-controlled assistant for Windows, inspired by J.A.R.V.I.S. and F.R.I.D.A.Y. from the Iron Man films. You talk, she answers out loud, and she can run your PC for you. Speech recognition, the language model and the voice all run **on your own computer**, with no cloud AI, no API keys and no GPU.

> "Friday, open Chrome." "Friday, set a 10 minute timer." "Friday, who is Albert Einstein?"

## Features

- Wake word (_Friday_ or _Jarvis_) and a 45 second follow-up window
- Interruptible speech: talk over her or press any key to stop her
- PC control: open and close apps, volume, brightness, screenshots, lock screen, timers, alarms, notes, battery and weather
- Protocols such as work mode, focus mode and night mode
- Contacts, WhatsApp messages and calls (she always asks before sending)
- Live Wikipedia, news, currency, world time and country facts
- Browser version and optional auto-start with Windows

## Tech stack

Python 3.12, Faster-Whisper (speech to text), Ollama with Qwen 2.5 (language model), Piper (voice), sounddevice, Flask.

## Project structure

```
main.py              voice loop
config.py            settings, personality, built-in answers
tools.py             command router: apps, timers, contacts, WhatsApp
knowledge.py         Wikipedia, news, currency, time zones
llm.py               local language model (Ollama)
asr.py               speech to text
tts.py               text to speech
audio_in.py          microphone and barge-in
memory.py            conversation memory
server.py, web/      browser version
run.bat              set up and start Friday
web.bat              start the web version
get_voice.bat        download the neural voice
```

## Quick start

1. Install **Python 3.12** (tick _Add to PATH_) and [Ollama](https://ollama.com/download/windows).
2. Download the model once: `ollama pull qwen2.5:3b-instruct`
3. Clone this repo and double-click **`run.bat`**.
4. When you see `[listening...]`, say **"Friday, what time is it?"**

Optional: run `get_voice.bat` for a better voice, `web.bat` for the browser version, and `install_autostart.bat` to start Friday with Windows.

## Notes

- Windows only for most PC actions.
- Contacts are stored in `people.json`, which is not uploaded to GitHub. Create it or say "Friday, add contact Rahul".
- She listens only after hearing her name, and nothing leaves your PC except lookups you ask for.
