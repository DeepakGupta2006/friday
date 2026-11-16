"""Pre-flight check: tells you exactly what is missing. Run:  python check.py"""
import os
import sys

import config

problems = []


def ok(msg):
    print(f"  [OK]   {msg}")


def info(msg):
    print(f"  [INFO] {msg}")


def bad(msg, fix):
    print(f"  [FAIL] {msg}")
    print(f"         -> {fix}")
    problems.append(msg)


print("\nFriday pre-flight check\n")

v = sys.version_info
if (3, 10) <= (v.major, v.minor) <= (3, 12):
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
else:
    bad(f"Python {v.major}.{v.minor} is not supported",
        "Install Python 3.12: https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe "
        "then delete the .venv folder and run run.bat again")


for module, pip_name in [("numpy", "numpy"), ("sounddevice", "sounddevice"),
                         ("faster_whisper", "faster-whisper"), ("ollama", "ollama"),
                         ("pyttsx3", "pyttsx3"), ("PIL", "pillow"), ("psutil", "psutil")]:
    try:
        __import__(module)
        ok(f"package {pip_name}")
    except Exception as e:
        bad(f"package {pip_name} ({e})", "pip install -r requirements.txt")


try:
    import ollama

    listing = ollama.Client(host=config.OLLAMA_HOST).list()
    entries = getattr(listing, "models", None)
    if entries is None:
        entries = listing.get("models", [])
    names = []
    for m in entries:
        name = getattr(m, "model", None) or (m.get("model") or m.get("name") if isinstance(m, dict) else None)
        if name:
            names.append(name)
    ok("Ollama is running")
    wanted = config.LLM_MODEL
    if wanted in names or f"{wanted}:latest" in names:
        ok(f"model {wanted} is downloaded")
    else:
        bad(f"model {wanted} is not downloaded", f"ollama pull {wanted}")
except Exception as e:
    bad(f"cannot reach Ollama at {config.OLLAMA_HOST} ({e})",
        "Install Ollama from https://ollama.com/download/windows and make sure it is running (llama icon in the tray)")

try:
    import sounddevice as sd

    device = sd.query_devices(config.MIC_DEVICE, kind="input")
    ok(f"microphone: {device['name']}")
except Exception as e:
    bad(f"no usable microphone ({e})", "Plug in / enable a mic in Windows Settings > Sound > Input")

# 5. Voice (optional upgrade)
if os.path.exists(config.PIPER_VOICE):
    try:
        import piper  

        ok(f"neural voice ready: {config.PIPER_VOICE_NAME}")
    except Exception:
        info("voice file found but the 'piper-tts' package is missing -> run get_voice.bat")
else:
    info("using the Windows voice. For a much better voice, double-click get_voice.bat")

print()
if problems:
    print(f"{len(problems)} problem(s) found. Fix the lines marked FAIL, then run again.\n")
    sys.exit(1)
print("Everything looks good.\n")
