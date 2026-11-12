"""Friday web server: talk to your assistant from a browser.

Run:  python server.py        then open  http://127.0.0.1:8000
The browser does the listening (mic) and speaking; this server runs the same
command router (tools.py) and local Ollama brain as the desktop version.
"""
import datetime
import json
import os
import socket
import threading

from flask import Flask, Response, jsonify, request, send_from_directory

import config
import llm
import tools
from memory import Memory

HOST = os.environ.get("FRIDAY_HOST", "127.0.0.1")   # 127.0.0.1 = this PC only
PORT = int(os.environ.get("FRIDAY_PORT", "8000"))
TOKEN = os.environ.get("FRIDAY_TOKEN", "")          # required when HOST is not local

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
app = Flask(__name__, static_folder=None)
memory = Memory()
lock = threading.Lock()          # one request at a time: she has one brain and one PC


def _authorized() -> bool:
    return not TOKEN or request.headers.get("X-Token") == TOKEN or request.args.get("token") == TOKEN


@app.before_request
def _guard():
    if request.path.startswith("/api/") and not _authorized():
        return jsonify(error="bad token"), 401


@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/hello")
def hello():
    h = datetime.datetime.now().hour
    part = "morning" if h < 12 else "afternoon" if h < 17 else "evening"
    t = config.USER_TITLE
    return jsonify(name=config.ASSISTANT_NAME, title=t,
                   greeting=f"Good {part}, {t}. {config.ASSISTANT_NAME} is online. How may I be of service?")


@app.get("/api/alerts")
def alerts():
    out = []
    try:
        while tools.has_due():
            out += tools.pop_due()
    except Exception:
        pass
    return jsonify(alerts=out)


def _system_prompt() -> str:
    now = datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
    p = config.system_prompt() + f"\nCurrent date and time: {now}."
    if memory.notes:
        p += "\nThings the user asked you to remember:\n" + "\n".join(f"- {n}" for n in memory.notes)
    return p


def _line(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False) + "\n"


@app.post("/api/chat")
def chat():
    text = (request.get_json(silent=True) or {}).get("text", "").strip()
    if not text:
        return jsonify(error="empty"), 400

    def generate():
        with lock:
            norm = tools.normalize(text)
            _, cmd = tools.strip_wake(norm)
            if not cmd:
                yield _line(type="reply", text=f"Yes, {config.USER_TITLE}?")
                yield _line(type="done")
                return
            try:
                result = tools.handle(cmd, memory)
            except Exception as e:                       # never crash the server on a bad command
                yield _line(type="reply", text=f"I hit a snag running that, {config.USER_TITLE}: {e}")
                yield _line(type="done")
                return
            if result is not None:
                reply, action = result
                if reply:
                    yield _line(type="reply", text=reply)
                yield _line(type="done", action=action)
                return

            # No built-in command matched: ask the local model, streamed sentence by sentence.
            messages = [{"role": "system", "content": _system_prompt()},
                        *memory.history, {"role": "user", "content": text}]
            buf, full = "", ""
            try:
                for tok in llm.stream_reply(messages):
                    buf += tok
                    done, buf = llm.sentence_chunks(buf)
                    for s in done:
                        full += s + " "
                        yield _line(type="reply", text=s)
                if buf.strip():
                    full += buf.strip()
                    yield _line(type="reply", text=buf.strip())
            except Exception:
                msg = (f"I cannot reach my language model, {config.USER_TITLE}. "
                       "Please check that Ollama is running.")
                yield _line(type="reply", text=msg)
                full = ""
            if full.strip():
                memory.add_turn(text, full.strip())
            yield _line(type="done")

    return Response(generate(), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "your-pc-ip"


if __name__ == "__main__":
    if HOST not in ("127.0.0.1", "localhost") and not TOKEN:
        raise SystemExit("Refusing to open Friday to your network without a password.\n"
                         "Set one first:  set FRIDAY_TOKEN=pick-a-long-secret   then run again.")
    try:
        llm.warm_up()
    except Exception:
        print("Note: Ollama is not answering yet. Built-in commands work; chat needs Ollama.")
    shown = "127.0.0.1" if HOST in ("127.0.0.1", "localhost") else _lan_ip()
    print(f"\n{config.ASSISTANT_NAME} web is up:  http://{shown}:{PORT}"
          + (f"/?token={TOKEN}" if TOKEN else "") + "\nPress Ctrl+C to stop.\n")
    app.run(host=HOST, port=PORT, threaded=True)
