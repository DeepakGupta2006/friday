"""Commands Friday handles instantly on this PC, without asking the AI model.

handle() returns None (let the AI model answer) or (reply_text, action)
where action is None, "exit" or "sleep".

WHAT SHE CAN DO (the first matching rule wins, in this order)
  Confirm       yes / no after "Shall I shut down?"
  Stop          stop, quiet, cancel                      Exit/standby  goodbye, go to sleep
  Personality   who are you, jokes, quotes, facts, banter (text lives in config.py)
  Protocols     work mode, focus mode, clean slate...    (config.py > ROUTINES)
  Apps          open / close / force close anything      websites, folders, projects, VS Code
  Screen        lock, wake the screen, screen off, stay awake  (unlock: refused, see below)
  Power         shutdown, restart, sleep, hibernate, sign out, empty recycle bin (always confirmed)
  Info          time, date, briefing, weather, battery, diagnostics, internet, IP, running apps, clipboard
  Math          "what is 25 times 4", "20 percent of 150"
  Sound/screen  volume, mute, music keys, brightness, screenshot, show desktop, switch window
  Time          timers, reminders, alarms at a clock time
  Notes         remember..., take a note..., read my notes, forget everything
  Misc          settings pages, flip a coin, roll a dice, random number, call me <name>
  People        contacts in people.json: "who is Rahul", "Rahul's number", birthdays, add/remove contact,
                WhatsApp a message, WhatsApp call (asks first), phone call, email  (all private, local)

UNLOCK: Windows does not let any program type into the lock screen, and a voice unlock
would let anyone's voice (or a recording) open your PC. So "unlock" is refused on purpose.
To unlock WITHOUT TYPING, use Windows Hello (face or fingerprint). Say "set up face unlock"
and she opens the right Settings page. (Dynamic lock only LOCKS when your phone walks away.)

To teach her a new app, add it to APPS (and PROCESSES so she can close it).
New website: SITES. New folder/project/protocol/joke/answer: config.py.
"""
import ast
import ctypes
import datetime
import json
import os
import random
import re
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

import config
import knowledge

_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_IS_WINDOWS = os.name == "nt"

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "claude": "https://claude.ai",
    "chatgpt": "https://chatgpt.com",
    "maps": "https://maps.google.com",
    "whatsapp web": "https://web.whatsapp.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://x.com",
    "reddit": "https://www.reddit.com",
    "stack overflow": "https://stackoverflow.com",
}

APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome",
    "edge": "msedge",
    "firefox": "firefox",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "command prompt": "cmd.exe",
    "terminal": "wt",
    "spotify": "spotify",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "camera": "microsoft.windows.camera:",
    "snipping tool": "snippingtool",
    "control panel": "control",
    "clock": "ms-clock:",
    "calendar": "outlookcal:",
    "mail": "outlookmail:",
    "store": "ms-windows-store:",
}

PROCESSES = {
    "notepad": ["notepad.exe"],
    "calculator": ["CalculatorApp.exe", "Calculator.exe", "calc.exe"],
    "paint": ["mspaint.exe"],
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "brave": ["brave.exe"],
    "browser": ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"],
    "browsers": ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "task manager": ["Taskmgr.exe"],
    "spotify": ["Spotify.exe"],
    "vs code": ["Code.exe"],
    "vscode": ["Code.exe"],
    "visual studio code": ["Code.exe"],
    "camera": ["WindowsCamera.exe"],
    "snipping tool": ["SnippingTool.exe"],
    "settings": ["SystemSettings.exe"],
    "whatsapp": ["WhatsApp.exe", "WhatsApp.Root.exe"],
    "discord": ["Discord.exe"],
    "vlc": ["vlc.exe"],
    "zoom": ["Zoom.exe"],
    "teams": ["ms-teams.exe", "Teams.exe"],
    "slack": ["slack.exe"],
    "telegram": ["Telegram.exe"],
    "steam": ["steam.exe"],
    "obs": ["obs64.exe"],
    "outlook": ["OUTLOOK.EXE"],
    "onenote": ["ONENOTE.EXE"],
    "media player": ["wmplayer.exe", "Microsoft.Media.Player.exe"],
    "photos": ["Microsoft.Photos.exe"],
}

PROTECTED = {"explorer", "file explorer", "windows explorer", "python", "pythonw", "cmd",
             "command prompt", "terminal", "windows terminal", "powershell", "ollama",
             "system", "taskbar", "friday", "jarvis", "yourself", "pycharm", "windows",
             "csrss", "winlogon", "svchost", "dwm", "lsass", "services", "wininit"}
_VAGUE = {"this", "it", "that", "everything", "all", "all windows", "window", "windows", "app", "apps",
          "all apps", "all programs"}


SETTINGS_PAGES = {
    "wifi": "ms-settings:network-wifi", "wi fi": "ms-settings:network-wifi",
    "network": "ms-settings:network", "bluetooth": "ms-settings:bluetooth",
    "display": "ms-settings:display", "sound": "ms-settings:sound",
    "battery": "ms-settings:batterysaver", "power": "ms-settings:powersleep",
    "update": "ms-settings:windowsupdate", "windows update": "ms-settings:windowsupdate",
    "apps": "ms-settings:appsfeatures", "privacy": "ms-settings:privacy",
    "microphone": "ms-settings:privacy-microphone", "storage": "ms-settings:storagesense",
    "default apps": "ms-settings:defaultapps", "notifications": "ms-settings:notifications",
    "personalization": "ms-settings:personalization", "lock screen": "ms-settings:lockscreen",
    "sign in": "ms-settings:signinoptions", "sign in options": "ms-settings:signinoptions",
    "windows hello": "ms-settings:signinoptions", "time": "ms-settings:dateandtime",
    "accounts": "ms-settings:yourinfo", "about": "ms-settings:about",
}



def normalize(text: str) -> str:
    t = text.lower().replace("'", "")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_ALIASES = sorted({normalize(a) for a in config.WAKE_ALIASES} | {normalize(config.WAKE_WORD)},
                  key=len, reverse=True)
_ALIAS_RE = "|".join(re.escape(a) for a in _ALIASES)
_LEAD = re.compile(r"^(?:(?:hey|ok|okay|hi|hello|yo)\s+)?(?:" + _ALIAS_RE + r")\b\s*")
_TRAIL = re.compile(r"\s*\b(?:" + _ALIAS_RE + r")$")
_NOT_WAKE_BEFORE = {"is", "its", "on", "this", "next", "last", "every", "happy", "good", "black"}


def strip_wake(norm: str):
    """Returns (heard_wake_word, rest_of_sentence)."""
    m = _LEAD.match(norm)
    if m:
        return True, norm[m.end():].strip()
    m = _TRAIL.search(norm)
    if m and m.start() > 0:
        before = norm[:m.start()].strip()
        if before.split()[-1] not in _NOT_WAKE_BEFORE:
            return True, before
    return False, norm


_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
          "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
          "nineteen": 19, "a": 1, "an": 1}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}


def to_int(text: str):
    """'5' -> 5, 'five' -> 5, 'twenty five' -> 25, 'a hundred' -> 100. None if not a number."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text in ("hundred", "one hundred", "a hundred"):
        return 100
    parts = text.split()
    if len(parts) == 1:
        if parts[0] in _UNITS:
            return _UNITS[parts[0]]
        return _TENS.get(parts[0])
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _UNITS and 0 < _UNITS[parts[1]] < 10:
        return _TENS[parts[0]] + _UNITS[parts[1]]
    return None


def _number_at_end(text: str):
    """Number made of the last one or two words: 'set a twenty five' -> 25, 'set a 10' -> 10."""
    words = text.split()
    for k in (2, 1):
        if len(words) >= k:
            n = to_int(" ".join(words[-k:]))
            if n is not None:
                return n
    return None


def _clock(now):
    return f"{now.hour % 12 or 12}:{now.minute:02d} {now:%p}"


def _start(target: str) -> bool:
    try:
        os.startfile(target)  
        return True
    except (OSError, AttributeError):
        return False


def _part_of_day() -> str:
    h = datetime.datetime.now().hour
    return "morning" if h < 12 else "afternoon" if h < 17 else "evening"


_last_pick: dict = {}


def _pick(key: str, items: list) -> str:
    """Random line that is not the same as the last one for this key."""
    i = random.randrange(len(items))
    if len(items) > 1 and _last_pick.get(key) == i:
        i = (i + 1) % len(items)
    _last_pick[key] = i
    return config._title_fmt(items[i])


_VK = {"vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD,
       "play_pause": 0xB3, "next": 0xB0, "prev": 0xB1,
       "win": 0x5B, "d": 0x44, "alt": 0x12, "tab": 0x09, "up": 0x26, "down": 0x28,
       "ctrl": 0x11, "shift": 0x10, "c": 0x43, "v": 0x56, "enter": 0x0D}


def _press(name: str, times: int = 1) -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(_VK[name], 0, 0, 0)
        user32.keybd_event(_VK[name], 0, 2, 0)   
        time.sleep(0.004)
    return True


def _hotkey(*names) -> bool:
    """Press keys together, e.g. _hotkey('win', 'd') for Win+D."""
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    for n in names:
        user32.keybd_event(_VK[n], 0, 0, 0)
    for n in reversed(names):
        user32.keybd_event(_VK[n], 0, 2, 0)
    return True


def lock_screen() -> bool:
    if os.name != "nt":
        return False
    ctypes.windll.user32.LockWorkStation()
    return True


def wake_display() -> bool:
    """Light up a sleeping screen. If the PC is LOCKED you still sign in yourself."""
    if os.name != "nt":
        return False
    k = ctypes.windll.kernel32
    k.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
    k.SetThreadExecutionState(0x00000002)          
    u = ctypes.windll.user32
    u.mouse_event(0x0001, 1, 0, 0, 0)              
    u.mouse_event(0x0001, -1, 0, 0, 0)
    return True


def display_off() -> bool:
    if os.name != "nt":
        return False
    ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)  
    return True


def keep_awake(on: bool) -> bool:
    """Stop Windows from sleeping or dimming while Friday runs."""
    if os.name != "nt":
        return False
    k = ctypes.windll.kernel32
    k.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
    flags = 0x80000000 | (0x00000001 | 0x00000002 if on else 0)   
    k.SetThreadExecutionState(flags)
    return True


UNLOCK_REPLY = ("I can't unlock Windows, {title}. The lock screen is protected on purpose, and a voice "
                "unlock would let anyone's voice, or a recording, open your machine. To unlock without typing, "
                "use Windows Hello with your face or fingerprint. Say set up face unlock and I'll open the page. "
                "If you only need the screen to light up, say wake the screen.")

HELLO_REPLY = ("The safe way to unlock without typing is Windows Hello, {title}. Opening sign in options. "
               "Choose face recognition or fingerprint, which needs a compatible camera or reader, then "
               "lock the screen and just look at it.")

DYNAMIC_LOCK_REPLY = ("Dynamic lock locks your PC when your paired phone walks away, {title}. It does not unlock it. "
                      "Opening sign in options. Pair your phone in Bluetooth settings first.")


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def battery_report():
    if os.name != "nt":
        return None
    s = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return None
    if s.BatteryLifePercent == 255 or s.BatteryFlag == 128:
        return "This PC has no battery, it runs on mains power."
    state = "and charging" if s.ACLineStatus == 1 else "and running on battery"
    return f"Battery is at {s.BatteryLifePercent} percent {state}."


def take_screenshot(title: str) -> str:
    try:
        from PIL import ImageGrab
    except ImportError:
        return "I need Pillow for that. Run pip install pillow, then restart me."
    try:
        os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(config.SCREENSHOT_DIR, f"screenshot_{datetime.datetime.now():%Y%m%d_%H%M%S}.png")
        ImageGrab.grab(all_screens=True).save(path)
        return f"Screenshot saved in your Pictures folder, {title}."
    except Exception as e:
        return f"I could not take the screenshot, {title}: {e}"


_WMO = {0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy",
        48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle",
        57: "freezing drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
        66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
        77: "snow grains", 80: "light showers", 81: "showers", 82: "heavy showers",
        85: "snow showers", 86: "heavy snow showers", 95: "a thunderstorm",
        96: "a thunderstorm with hail", 99: "a thunderstorm with hail"}


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "friday-assistant"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read().decode("utf-8"))


def weather_report(city: str) -> str:
    """Free Open-Meteo service, no API key. Raises on network problems."""
    geo = _get_json("https://geocoding-api.open-meteo.com/v1/search?name="
                    + urllib.parse.quote(city) + "&count=1")
    results = geo.get("results")
    if not results:
        return f"I could not find a place called {city}."
    place = results[0]
    w = _get_json("https://api.open-meteo.com/v1/forecast"
                  f"?latitude={place['latitude']}&longitude={place['longitude']}"
                  "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code"
                  "&timezone=auto")
    cur = w["current"]
    desc = _WMO.get(int(cur.get("weather_code", 0)), "unsettled")
    return (f"In {place['name']} it's {round(cur['temperature_2m'])} degrees with {desc}. "
            f"It feels like {round(cur['apparent_temperature'])}, humidity {round(cur['relative_humidity_2m'])} percent.")


def _ps(script: str, timeout: int = 10):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, text=True, timeout=timeout, creationflags=_NOWIN)
    return r.returncode, r.stdout.strip()


def get_brightness():
    """Laptop screen brightness 0-100, or None (desktop monitors do not support this)."""
    if os.name != "nt":
        return None
    try:
        code, out = _ps("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness")
        return int(out.split()[0]) if code == 0 and out else None
    except Exception:
        return None


def set_brightness(level: int) -> bool:
    if os.name != "nt":
        return False
    try:
        code, _ = _ps("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                      f".WmiSetBrightness(1,{int(max(0, min(100, level)))})")
        return code == 0
    except Exception:
        return False


def system_status(title: str) -> str:
    try:
        import psutil
    except ImportError:
        return f"I need psutil for diagnostics, {title}. Run pip install psutil, then restart me."
    cpu = psutil.cpu_percent(interval=0.4)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage(os.path.abspath(os.sep)).percent
    warn = []
    if cpu > 85:
        warn.append("the processor is working hard")
    if mem > 90:
        warn.append("memory is nearly full")
    if disk > 92:
        warn.append("the disk is nearly full")
    head = (f"All systems nominal, {title}." if not warn
            else f"Mostly nominal, {title}, though " + " and ".join(warn) + ".")
    text = f"{head} Processor at {cpu:.0f} percent, memory at {mem:.0f}, disk at {disk:.0f}."
    b = battery_report()
    return text + (" " + b if b else "")


def is_online() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return True
    except OSError:
        return False


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))        
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def clipboard_text():
    if os.name != "nt":
        return None
    try:
        code, out = _ps("Get-Clipboard", timeout=6)
        return out if code == 0 else None
    except Exception:
        return None


_RUNNING_IGNORE = {"applicationframehost", "textinputhost", "systemsettings", "searchhost",
                   "startmenuexperiencehost", "shellexperiencehost", "lockapp", "widgets",
                   "python", "pythonw", "explorer"}


def running_apps():
    """Names of apps that have a visible window."""
    if os.name != "nt":
        return None
    try:
        code, out = _ps("Get-Process | Where-Object { $_.MainWindowTitle } | "
                        "Select-Object -ExpandProperty ProcessName | Sort-Object -Unique", timeout=10)
    except Exception:
        return None
    if code != 0:
        return None
    return [n.strip() for n in out.splitlines() if n.strip() and n.strip().lower() not in _RUNNING_IGNORE]


_start_index = None


def _build_start_index():
    global _start_index
    idx = {}
    roots = [os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
             os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith(".lnk"):
                    stem = normalize(os.path.splitext(f)[0])
                    if stem and "uninstall" not in stem:
                        idx.setdefault(stem, os.path.join(dirpath, f))
    _start_index = idx


def find_start_menu(name: str):
    """Look for a Start Menu shortcut: exact name, then starts with, then contains."""
    if _start_index is None:
        _build_start_index()
    if name in _start_index:
        return _start_index[name]
    for stem in sorted(_start_index, key=len):
        if stem.startswith(name):
            return _start_index[stem]
    for stem in sorted(_start_index, key=len):
        if name in stem:
            return _start_index[stem]
    return None


def find_store_app(name: str):
    """Microsoft Store apps are not Start Menu shortcuts. Ask Windows for their ID."""
    if os.name != "nt" or not re.fullmatch(r"[a-z0-9 ]{2,30}", name):
        return None
    try:
        code, out = _ps("Get-StartApps | Where-Object { $_.Name -like '*" + name
                        + "*' } | Select-Object -First 1 -ExpandProperty AppID", timeout=12)
        return out.splitlines()[0].strip() if code == 0 and out else None
    except Exception:
        return None


def open_by_search(name: str) -> bool:
    path = find_start_menu(name)
    if path and _start(path):
        return True
    app_id = find_store_app(name)
    if app_id:
        try:
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + app_id])
            return True
        except OSError:
            return False
    return False


def open_target(name: str, is_project: bool = False):
    """Open a website, app, folder, project or any Start Menu app.
    Returns the kind that was opened ('site', 'app', 'folder', 'project', 'search') or None."""
    if not is_project:
        if name in SITES:
            webbrowser.open(SITES[name])
            return "site"
        if name in APPS:
            if _start(APPS[name]) or open_by_search(name):
                return "app"
            return None
        if name in config.FOLDERS:
            return "folder" if _start(config.FOLDERS[name]) else None
    if name in config.PROJECTS:
        return "project" if _start(config.PROJECTS[name]) else None
    if not is_project and open_by_search(name):
        return "search"
    return None


_CLOSE_SAFE_NAME = re.compile(r"[a-z0-9 ]{2,25}")
_PS_SKIP = ("explorer,python,pythonw,cmd,powershell,pwsh,conhost,ollama,csrss,winlogon,svchost,"
            "dwm,lsass,services,wininit,WindowsTerminal,pycharm64,idea64")


def close_app(name: str, force: bool = False) -> str:
    """Returns 'closed', 'notrunning', 'protected', 'needsforce', 'unknown' or 'unsupported'."""
    if name in PROTECTED:
        return "protected"
    if os.name != "nt":
        return "unsupported"
    exes = PROCESSES.get(name)
    if exes:
        closed, needs_force = False, False
        for exe in exes:
            cmd = ["taskkill", "/IM", exe, "/T"] + (["/F"] if force else [])
            r = subprocess.run(cmd, capture_output=True, text=True, creationflags=_NOWIN)
            if r.returncode == 0:
                closed = True
            elif "/F" in (r.stderr or "") + (r.stdout or ""):
                needs_force = True
        if closed:
            return "closed"
        return "needsforce" if needs_force else "notrunning"
    if not _CLOSE_SAFE_NAME.fullmatch(name):
        return "unknown"
    
    action = "$x.Kill()" if force else "[void]$x.CloseMainWindow()"
    script = (f"$n='{name}'; $skip='{_PS_SKIP}'.Split(','); "
              "$p = Get-Process | Where-Object { $_.MainWindowTitle -and $skip -notcontains $_.ProcessName "
              "-and ($_.ProcessName -like \"*$n*\" -or $_.MainWindowTitle -like \"*$n*\") }; "
              "if (-not $p) { exit 3 }; foreach ($x in $p) { " + action + " }")
    try:
        code, _ = _ps(script, timeout=12)
    except Exception:
        return "unknown"
    return "closed" if code == 0 else "notrunning" if code == 3 else "unknown"


def run_routine(key: str) -> str:
    r = config.ROUTINES[key]
    for name in r.get("close", []):
        close_app(name)
    for name in r.get("open", []):
        open_target(name)
    if r.get("lock"):
        lock_screen()
    return config._title_fmt(r.get("say", "Protocol engaged, {title}."))


_ROUTINE_RE = re.compile(r"^(?:(?:initiate|activate|start|run|engage|enable|begin|turn on|switch to|enter|go to)\s+)?"
                         r"(?:the )?(.+?)\s+(?:mode|protocol)(?: on)?$")


_pending = {"action": None, "payload": None, "until": 0.0}
_CONFIRM = re.compile(r"^(yes|yes please|yeah|yep|confirm|confirmed|do it|go ahead|affirmative|proceed|please do)$")
_DENY = re.compile(r"^(no|nope|cancel|never mind|nevermind|abort|negative|dont|do not|not now)$")
_POWER_LABEL = {"shutdown": "shut the computer down", "restart": "restart the computer",
                "sleep": "put the computer to sleep", "hibernate": "hibernate the computer",
                "signout": "sign you out", "recyclebin": "empty the recycle bin"}


def _run_power(action: str, title: str) -> str:
    if os.name != "nt":
        return "I can only do that on a Windows PC."
    delay = str(config.SHUTDOWN_DELAY_S)
    try:
        if action == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", delay], creationflags=_NOWIN)
            return f"Shutting down in {delay} seconds, {title}. Say cancel shutdown to stop it."
        if action == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", delay], creationflags=_NOWIN)
            return f"Restarting in {delay} seconds, {title}. Say cancel shutdown to stop it."
        if action == "signout":
            subprocess.Popen(["shutdown", "/l"], creationflags=_NOWIN)
            return f"Signing you out, {title}."
        if action == "sleep":
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return f"Going to sleep, {title}."
        if action == "hibernate":
            subprocess.Popen(["shutdown", "/h"], creationflags=_NOWIN)
            return f"Hibernating, {title}."
        if action == "recyclebin":
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)   
            return f"Recycle bin emptied, {title}."
    except OSError as e:
        return f"That did not work, {title}: {e}"
    return "I did not understand that power command."


def _ask_confirm(action: str, question: str, payload=None) -> str:
    """Remember what she is about to do and wait for a yes (see the top of handle())."""
    _pending["action"] = action
    _pending["payload"] = payload
    _pending["until"] = time.time() + config.CONFIRM_WINDOW_S
    return f"{question} Say yes to confirm."


def _ask_power(action: str, title: str) -> str:
    return _ask_confirm(action, f"Shall I {_POWER_LABEL[action]}, {title}?")


def _run_confirmed(action: str, payload, title: str) -> str:
    """Do the thing the user just said yes to."""
    if action in _POWER_LABEL:
        return _run_power(action, title)
    if action == "wa_message":
        return whatsapp_send(payload["person"], payload["text"], title)
    if action == "wa_call":
        return whatsapp_call(payload["person"], payload.get("video", False), title)
    if action == "phone_call":
        return phone_call(payload["person"], title)
    if action == "delete_person":
        return delete_person(payload["person"], title)
    return "I did not understand that."


_alarms: list = []
_alarm_lock = threading.Lock()
_UNIT_RE = r"(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours)"


def _seconds(amount: int, unit: str) -> int:
    if unit.startswith("h"):
        return amount * 3600
    if unit.startswith("m"):
        return amount * 60
    return amount


def _duration_text(amount: int, unit: str) -> str:
    unit = "hour" if unit.startswith("h") else "minute" if unit.startswith("m") else "second"
    return f"{amount} {unit}{'' if amount == 1 else 's'}"


def _add_alarm(seconds: float, message: str):
    with _alarm_lock:
        _alarms.append((time.time() + seconds, message))


def has_due() -> bool:
    with _alarm_lock:
        return any(due <= time.time() for due, _ in _alarms)


def pop_due() -> list:
    with _alarm_lock:
        now = time.time()
        due = [m for t, m in _alarms if t <= now]
        _alarms[:] = [(t, m) for t, m in _alarms if t > now]
    return due


def next_clock_time(hour: int, minute: int, suffix: str = ""):
    """Next time the clock shows hour:minute. Without am/pm the soonest of the two. None if invalid."""
    if not (0 <= minute <= 59) or not (0 <= hour <= 23):
        return None
    now = datetime.datetime.now()
    sfx = suffix.replace(" ", "")
    if sfx in ("am", "pm"):
        if hour > 12 or hour == 0:
            return None
        hours = [hour % 12 + (12 if sfx == "pm" else 0)]
    elif hour > 12 or hour == 0:
        hours = [hour]
    else:
        hours = [hour % 12, hour % 12 + 12]
    best = None
    for h in hours:
        t = now.replace(hour=h, minute=minute, second=0, microsecond=0)
        if t <= now:
            t += datetime.timedelta(days=1)
        if best is None or t < best:
            best = t
    return best


_OPS = {"plus": "+", "add": "+", "minus": "-", "subtract": "-", "times": "*", "x": "*", "into": "*",
        "over": "/", "mod": "%", "power": "**"}


def _fmt_number(x) -> str:
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e15:
            return str(int(x))
        return f"{x:.4f}".rstrip("0").rstrip(".")
    return str(x)


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    if isinstance(node, ast.BinOp):
        a, b = _safe_eval(node.left), _safe_eval(node.right)
        op = type(node.op)
        if op is ast.Add:
            return a + b
        if op is ast.Sub:
            return a - b
        if op is ast.Mult:
            return a * b
        if op is ast.Div:
            return a / b
        if op is ast.Mod:
            return a % b
        if op is ast.Pow:
            if abs(b) > 64 or abs(a) > 10 ** 6:
                raise ValueError("too large")
            return a ** b
    raise ValueError("not allowed")


def calculate(expr: str):
    """Returns the answer as text, 'divzero', or None if the sentence is not maths."""
    s = (expr.replace("multiplied by", "times").replace("divided by", "over")
         .replace("to the power of", "power").replace("raised to", "power")
         .replace("take away", "minus"))
    m = re.fullmatch(r"(.+?) percent of (.+)", s)
    if m:
        a, b = to_int(m.group(1)), to_int(m.group(2))
        return None if a is None or b is None else _fmt_number(a * b / 100)
    toks = s.split()
    items, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in ("a", "an", "the"):
            i += 1
            continue
        if t in ("squared", "cubed"):
            items += ["**", "2" if t == "squared" else "3"]
        elif t in _OPS:
            items.append(_OPS[t])
        elif t.isdigit():
            items.append(str(int(t)))
        elif t in _TENS and i + 1 < len(toks) and toks[i + 1] in _UNITS and 0 < _UNITS[toks[i + 1]] < 10:
            items.append(str(_TENS[t] + _UNITS[toks[i + 1]]))
            i += 1
        elif t in _UNITS:
            items.append(str(_UNITS[t]))
        elif t in _TENS:
            items.append(str(_TENS[t]))
        elif t == "hundred":
            items.append("100")
        else:
            return None
        i += 1
    if len(items) < 3 or len(items) % 2 == 0:
        return None
    for k, it in enumerate(items):
        is_number = it.isdigit()
        if (k % 2 == 0) != is_number:
            return None
    try:
        return _fmt_number(_safe_eval(ast.parse("".join(items), mode="eval")))
    except ZeroDivisionError:
        return "divzero"
    except (ValueError, SyntaxError, OverflowError):
        return None


_people_cache = {"mtime": None, "data": []}
_MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
           "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
           "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
           "sept": 9, "oct": 10, "nov": 11, "dec": 12}
_MONTH_RE = "(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + ")"

_NAME_STOP = {"me", "my", "you", "your", "him", "her", "them", "it", "the", "and", "for", "with",
              "friday", "jarvis", "what", "who", "when", "where", "how", "call", "open", "tell", "send",
              "message", "whatsapp", "email", "phone", "number", "birthday", "contact", "contacts"}


def load_people(force: bool = False) -> list:
    """Read people.json (again only if the file changed). Never raises."""
    path = config.PEOPLE_FILE
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        _people_cache.update(mtime=None, data=[])
        return _people_cache["data"]
    if force or mtime != _people_cache["mtime"]:
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            return _people_cache["data"]          
        items = raw.get("people", []) if isinstance(raw, dict) else raw
        data = [p for p in items if isinstance(p, dict) and str(p.get("name", "")).strip()]
        _people_cache.update(mtime=mtime, data=data)
    return _people_cache["data"]


def save_people(people: list):
    path = config.PEOPLE_FILE
    old_help = ""
    try:
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
        old_help = old.get("_help", "") if isinstance(old, dict) else ""
    except (OSError, ValueError):
        pass
    body = {"_help": old_help, "people": people} if old_help else {"people": people}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    _people_cache.update(mtime=os.path.getmtime(path), data=people)


def _aliases(p: dict) -> set:
    names = set()
    full = normalize(str(p.get("name", "")))
    if full:
        names.add(full)
        first = full.split()[0]
        if len(first) >= 3:
            names.add(first)
    for a in p.get("aliases", []) or []:
        na = normalize(str(a))
        if na:
            names.add(na)
    return {n for n in names if len(n) >= 2 and n not in _NAME_STOP}


def find_person(text: str):
    """Longest known name or nickname inside the sentence -> (person, start, end), or None."""
    best = None
    for p in load_people():
        for alias in _aliases(p):
            m = re.search(r"\b" + re.escape(alias) + r"s?\b", text)
            if m and (best is None or len(alias) > best[3]):
                best = (p, m.start(), m.end(), len(alias))
    return best[:3] if best else None


def wa_number(phone):
    """Digits for WhatsApp links: country code included, no plus, no zeros in front. None if empty."""
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if raw.startswith("+"):
        return digits
    if digits.startswith("00"):
        return digits[2:]
    digits = digits.lstrip("0")
    if len(digits) <= 10:
        return config.DEFAULT_COUNTRY_CODE + digits
    return digits


def _person_number(p: dict):
    return wa_number(p.get("whatsapp") or p.get("phone"))


def _speak_digits(phone: str) -> str:
    d = re.sub(r"\D", "", str(phone))
    return ", ".join(" ".join(d[i:i + 5]) for i in range(0, len(d), 5))


def _parse_birthday(s):
    m = re.fullmatch(r"(?:(\d{4})-)?(\d{1,2})-(\d{1,2})", str(s or "").strip())
    if not m:
        return None
    year = int(m.group(1)) if m.group(1) else None
    mo, d = int(m.group(2)), int(m.group(3))
    try:
        datetime.date(2000, mo, d)
    except ValueError:
        return None
    return year, mo, d


def next_birthday(p: dict, today=None):
    """(date of the next birthday, age they turn or None) or None if no birthday is saved."""
    b = _parse_birthday(p.get("birthday"))
    if not b:
        return None
    year, mo, d = b
    today = today or datetime.date.today()
    for y in (today.year, today.year + 1):
        try:
            dt = datetime.date(y, mo, d)
        except ValueError:                      
            dt = datetime.date(y, 3, 1)
        if dt >= today:
            return dt, (y - year if year else None)
    return None


def _when(dt, today=None) -> str:
    days = (dt - (today or datetime.date.today())).days
    return "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"


def upcoming_birthdays(days: int, today=None) -> list:
    today = today or datetime.date.today()
    out = []
    for p in load_people():
        nb = next_birthday(p, today)
        if nb and (nb[0] - today).days <= days:
            out.append((p, nb[0], nb[1]))
    return sorted(out, key=lambda x: x[1])


def birthday_text(p: dict) -> str:
    nb = next_birthday(p)
    if not nb:
        return ""
    dt, age = nb
    text = f"{p['name']}'s birthday is {dt.day} {dt:%B}"
    if age:
        text += f", turning {age}"
    return text + f". That is {_when(dt)}."


def describe_person(p: dict, title: str) -> str:
    name = p["name"]
    rel = str(p.get("relation") or "").strip()
    bits = [f"{name} is your {rel}." if rel else f"{name}."]
    if p.get("company"):
        bits.append(f"Works at {p['company']}.")
    if p.get("city"):
        bits.append(f"Lives in {p['city']}.")
    bt = birthday_text(p)
    if bt:
        bits.append(bt)
    if p.get("notes"):
        bits.append(f"Notes: {p['notes']}")
    if len(bits) == 1:
        bits.append(f"That is all I have, {title}. You can add more in people.json.")
    return " ".join(bits)


def add_person(name: str, phone: str = ""):
    """Create a contact. Returns the new entry, or None if the name already exists."""
    people = list(load_people())
    low = normalize(name)
    for p in people:
        if low in _aliases(p) or low == normalize(p["name"]):
            return None
    entry = {"name": name.title(), "aliases": [], "relation": "", "phone": re.sub(r"\s", "", phone or ""),
             "email": "", "birthday": "", "company": "", "city": "", "notes": ""}
    people.append(entry)
    save_people(people)
    return entry


def delete_person(p: dict, title: str) -> str:
    people = [x for x in load_people() if x is not p]
    save_people(people)
    return f"{p['name']} removed from your contacts, {title}."



def _wa_links(number: str, text=None):
    q = urllib.parse.quote(text) if text else None
    app = f"whatsapp://send?phone={number}" + (f"&text={q}" if q else "")
    web = f"https://wa.me/{number}" + (f"?text={q}" if q else "")
    return app, web


def whatsapp_open(number: str, text=None) -> str:
    """Open the chat. Returns 'app' (WhatsApp Desktop) or 'web' (browser, the fallback)."""
    app, web = _wa_links(number, text)
    if _start(app):
        return "app"
    webbrowser.open(web)
    return "web"


def _later(delay: float, fn):
    t = threading.Timer(delay, fn)       
    t.daemon = True
    t.start()


def whatsapp_send(p: dict, text: str, title: str) -> str:
    number = _person_number(p)
    if not number:
        return f"I don't have a number for {p['name']}, {title}."
    how = whatsapp_open(number, text)
    if how == "app" and config.WHATSAPP_AUTO_SEND:
        _later(config.WHATSAPP_LOAD_DELAY_S, lambda: _hotkey("enter"))
        return f"Sending your message to {p['name']} on WhatsApp, {title}."
    return f"Your message to {p['name']} is ready in WhatsApp, {title}. Press Enter to send it."


def whatsapp_call(p: dict, video: bool, title: str) -> str:
    number = _person_number(p)
    if not number:
        return f"I don't have a number for {p['name']}, {title}."
    how = whatsapp_open(number)
    if how == "app" and _IS_WINDOWS:
        keys = ("ctrl", "shift", "v" if video else "c")        
        _later(config.WHATSAPP_CALL_DELAY_S, lambda: _hotkey(*keys))
        return (f"{'Video calling' if video else 'Calling'} {p['name']} on WhatsApp, {title}. "
                "If it does not ring, tap the call icon.")
    return f"I've opened the chat with {p['name']}, {title}. Tap the call icon to start the call."


def phone_call(p: dict, title: str) -> str:
    number = _person_number(p)
    if not number:
        return f"I don't have a number for {p['name']}, {title}."
    if _start("tel:+" + number):
        return f"Dialling {p['name']}, {title}."
    return (f"I can't place phone calls from this PC, {title}. It needs Phone Link set up. "
            "Say WhatsApp call instead.")


def email_person(p: dict, body: str, title: str) -> str:
    addr = str(p.get("email") or "").strip()
    if not addr:
        return f"I don't have an email for {p['name']}, {title}."
    url = "mailto:" + urllib.parse.quote(addr, safe="@") + ("?body=" + urllib.parse.quote(body) if body else "")
    webbrowser.open(url)
    return f"Opening a new email to {p['name']}, {title}."


def _parse_date_words(text: str):
    """'15 march', '15th of march', 'march 15' -> (month, day), or None."""
    m = re.search(r"\b(\d{1,2})(?: ?(?:st|nd|rd|th))?(?: of)? " + _MONTH_RE + r"\b", text)
    if m:
        day, mon = int(m.group(1)), _MONTHS[m.group(2)]
    else:
        m = re.search(r"\b" + _MONTH_RE + r" (\d{1,2})(?: ?(?:st|nd|rd|th))?\b", text)
        if not m:
            return None
        mon, day = _MONTHS[m.group(1)], int(m.group(2))
    try:
        datetime.date(2000, mon, day)
    except ValueError:
        return None
    return mon, day


def _bday_line(p, dt, age) -> str:
    return f"{p['name']} {_when(dt)}" + (f", turning {age}" if age else "")


def _birthday_brief() -> str:
    ups = upcoming_birthdays(7)
    if not ups:
        return ""
    return "Birthdays: " + "; ".join(_bday_line(*u) for u in ups[:3]) + "."


def _handle_people(cmd: str, title: str):
    """Contacts, WhatsApp, calls, email, birthdays. Returns (reply, action) or None."""
    
    if re.search(r"\b(?:upcoming birthdays?|any birthdays?|whose birthday|birthdays? (?:today|this week|coming up|soon|next)|next birthday|who has a birthday)\b", cmd):
        ups = upcoming_birthdays(config.BIRTHDAY_LOOKAHEAD_DAYS)
        if not ups:
            return f"No birthdays in the next {config.BIRTHDAY_LOOKAHEAD_DAYS} days, {title}.", None
        return "Coming up: " + "; ".join(_bday_line(*u) for u in ups[:5]) + ".", None
    if re.search(r"\b(?:reload|refresh) (?:my |the )?(?:contacts|people)\b", cmd):
        return f"Contacts reloaded, {title}. I know {len(load_people(force=True))} people.", None
    if re.search(r"\b(?:list|show|read) (?:out )?(?:all )?(?:my )?(?:contacts|people)\b|\bhow many (?:contacts|people)\b|\bwho do you know\b", cmd):
        names = [p["name"] for p in load_people()]
        if not names:
            return f"Your contacts file is empty, {title}. Say add contact, then a name.", None
        return (f"I know {len(names)} people: " + ", ".join(names[:10]) + (" and others" if len(names) > 10 else "") + "."), None
    if re.fullmatch(r"(?:open|show) (?:my |the )?(?:contacts|people) file", cmd):
        if os.path.exists(config.PEOPLE_FILE) and _start(config.PEOPLE_FILE):
            return config.ack(), None
        return f"I could not open the contacts file, {title}.", None
    m = re.match(r"^(?:add|save|create) (?:a |new |a new )?contact (?:called |named |for )?([a-z][a-z ]{1,28}?)"
                 r"(?: (?:with )?(?:the )?(?:phone |mobile |phone number |number )(?:is )?([0-9][0-9 ]{5,18}[0-9]))?$", cmd)
    if m:
        entry = add_person(m.group(1).strip(), m.group(2) or "")
        if entry is None:
            return f"I already have {m.group(1).strip()} in your contacts, {title}.", None
        if entry["phone"]:
            return f"Added {entry['name']} with that number, {title}.", None
        return f"Added {entry['name']}, {title}. Say set {m.group(1).strip()} number to, followed by the digits.", None

    
    found = find_person(cmd)
    if not found:
        m = re.match(r"^(?:(?:video )?call|dial|ring) (?!me\b|a\b|an\b|the\b|my\b|it\b|back\b|up\b)([a-z]+(?: [a-z]+)?)(?: on whatsapp)?$", cmd)
        if m:
            return (f"I don't have {m.group(1)} in your contacts, {title}. "
                    f"Say add contact {m.group(1)} number, followed by the digits."), None
        return None
    p, s, e = found
    name = p["name"]
    before, after = cmd[:s].strip(), cmd[e:].strip()

    
    digits = re.search(r"([0-9][0-9 ]{5,18}[0-9])$", after)
    if digits and re.search(r"\b(?:set|change|update|save|add)\b", before) and "number" in cmd:
        p["phone"] = re.sub(r"\s", "", digits.group(1))
        save_people(load_people())
        return f"Saved the new number for {name}, {title}.", None
    if "birthday" in cmd and re.search(r"\b(?:set|add|change|update|save|is|on)\b", cmd):
        date = _parse_date_words(after)
        if date:
            year = re.search(r"\b(19\d\d|20\d\d)\b", after)
            old = _parse_birthday(p.get("birthday"))
            y = year.group(1) if year else (old[0] if old and old[0] else None)
            p["birthday"] = (f"{y}-" if y else "") + f"{date[0]:02d}-{date[1]:02d}"
            save_people(load_people())
            return f"Noted, {title}. {name}'s birthday is {date[1]} {datetime.date(2000, date[0], 1):%B}.", None
    if before == "" and after.startswith("is my "):
        rel = after[len("is my "):].strip()
        if re.fullmatch(r"[a-z ]{2,25}", rel):
            p["relation"] = rel
            save_people(load_people())
            return f"Understood, {title}. {name} is your {rel}.", None
    if re.fullmatch(r"(?:add (?:a )?note|make a note|note|remember|write down|jot down)(?: down)? (?:about|on|for|regarding)", before):
        text = re.sub(r"^(?:that|how)\s+", "", after).strip()
        if not text:
            return f"What should I note about {name}, {title}?", None
        p["notes"] = (str(p.get("notes") or "").rstrip(" .") + "; " if p.get("notes") else "") + text
        save_people(load_people())
        return f"Noted about {name}, {title}.", None
    if re.fullmatch(r"(?:remove|delete|forget)(?: the)?(?: contact)?", before) and after in ("", "from my contacts", "from contacts", "from the contacts"):
        return _ask_confirm("delete_person", f"Shall I remove {name} from your contacts, {title}?", {"person": p}), None

    
    if re.search(r"\b(?:number|phone number|mobile number|contact number)\b", cmd) and not re.search(r"\b(?:call|dial|ring|whatsapp|message|text|send)\b", before):
        if not p.get("phone") and not p.get("whatsapp"):
            return f"I don't have a number for {name}, {title}.", None
        return f"{name}'s number is {_speak_digits(p.get('phone') or p.get('whatsapp'))}.", None

    
    if re.search(r"\b(?:email|e mail|mail)\b", before):
        body = re.sub(r"^(?:saying|say|that says|that|about|with)\s+", "", after).strip()
        return email_person(p, body, title), None
    if re.search(r"\b(?:call|dial|ring)\b", before):
        if not _person_number(p):
            return f"I don't have a number for {name}, {title}.", None
        video = "video" in cmd
        by_phone = bool(re.search(r"\b(?:phone call|normal call|regular call|dial|mobile call|by phone|on the phone|on phone)\b", cmd)) \
            or (config.CALL_VIA == "phone" and "whatsapp" not in cmd)
        if by_phone:
            if config.CONFIRM_CALLS:
                return _ask_confirm("phone_call", f"Shall I phone {name}, {title}?", {"person": p}), None
            return phone_call(p, title), None
        if config.CONFIRM_CALLS:
            kind = "video call" if video else "call"
            return _ask_confirm("wa_call", f"Shall I {kind} {name} on WhatsApp, {title}?", {"person": p, "video": video}), None
        return whatsapp_call(p, video, title), None
    if re.search(r"\b(?:tell me about|what do you know about|who is|whos|describe|details (?:of|about|on)|info(?:rmation)? (?:on|about|of)|profile (?:of|for))\b", before):
        return describe_person(p, title), None
    if re.search(r"\b(?:send|write|text|message|msg|whatsapp|chat)\b|\btell\b(?! me\b)", before):
        body = re.sub(r"^(?:saying|say|that says|that|to say|telling|tell him|tell her|tell them|with|message)\s+", "", after).strip()
        if not body:
            number = _person_number(p)
            if not number:
                return f"I don't have a number for {name}, {title}.", None
            whatsapp_open(number)
            return f"Opening your WhatsApp chat with {name}, {title}.", None
        body = body[0].upper() + body[1:]
        if config.CONFIRM_MESSAGES:
            return _ask_confirm("wa_message", f"Shall I send {name} this on WhatsApp: {body}?", {"person": p, "text": body}), None
        return whatsapp_send(p, body, title), None
    if re.search(r"\b(?:birthday|born|how old|age)\b", cmd):
        bt = birthday_text(p)
        return (bt or f"I don't have a birthday for {name}, {title}. Say {name} birthday is, then the date."), None
    if re.search(r"\b(?:address|live|lives|city)\b", cmd):
        where = p.get("address") or p.get("city")
        return (f"{name} lives in {where}." if where else f"I don't have an address for {name}, {title}."), None
    if re.search(r"\b(?:work|works|company|job|office)\b", cmd):
        return (f"{name} works at {p['company']}." if p.get("company") else f"I don't know where {name} works, {title}."), None
    if re.search(r"\b(?:who is|whos|tell me about|about|details|info|information|profile|describe|what do you know about)\b", cmd):
        return describe_person(p, title), None
    return None


def _briefing(memory) -> str:
    now = datetime.datetime.now()
    parts = [f"It's {_clock(now)} on {now:%A}, {now.day} {now:%B}."]
    try:
        parts.append(weather_report(config.HOME_CITY))
    except Exception:
        pass
    b = battery_report()
    if b:
        parts.append(b)
    bd = _birthday_brief()
    if bd:
        parts.append(bd)
    n = len(memory.notes)
    if n:
        parts.append(f"You have {n} saved note{'s' if n != 1 else ''}.")
    return " ".join(parts)


def _can_do(ok: bool, title: str, what: str = "that") -> str:
    return config.ack() if ok else f"I can only do {what} on Windows, {title}."


def handle(cmd: str, memory):
    title = config.USER_TITLE

    
    if _pending["action"]:
        action, payload = _pending["action"], _pending.get("payload")
        live = time.time() <= _pending["until"]
        _pending["action"], _pending["payload"] = None, None
        if live and _CONFIRM.match(cmd):
            return _run_confirmed(action, payload, title), None
        if live and _DENY.match(cmd):
            return f"Standing down, {title}.", None
        

    
    if re.match(r"^(?:ok |okay )?(stop|stop talking|stop it|be quiet|quiet|enough|cancel|never mind|nevermind|shut up)$", cmd):
        return "", None

    
    if re.match(r"^(goodbye|good bye|bye|bye bye|exit|quit|shut down|shutdown|power down)(?: for now| now| please)?$", cmd):
        return f"Goodbye, {title}. Going offline.", "exit"
    if re.match(r"^(go to sleep|standby|stand by|sleep mode|sleep now)\b", cmd):
        return f"Standing by, {title}. Say my name when you need me.", "sleep"

    
    if re.fullmatch(r"(?:tell me (?:a )?joke|tell me another joke|joke|another joke|make me laugh|say something funny|tell me something funny)", cmd):
        return _pick("joke", config.JOKES), None
    if re.fullmatch(r"(?:give me a quote|tell me a quote|quote|inspire me|motivate me|say something inspiring)", cmd):
        return _pick("quote", config.QUOTES), None
    if re.fullmatch(r"(?:fun fact|give me a fun fact|tell me a fun fact|tell me something interesting|random fact|tell me a fact)", cmd):
        return _pick("fact", config.FACTS), None
    for pattern, answer in list(config.INFO) + list(config.FUN):
        if re.fullmatch(pattern + r"(?: please| sir)?", cmd):
            return config._title_fmt(answer), None

    
    if re.fullmatch(r"(?:thank you|thanks|thank you very much|thanks a lot|cheers|much appreciated)", cmd):
        return f"My pleasure sir, {title}.", None
    if re.fullmatch(r"(?:are you there|you there|are you awake|status)", cmd):
        return f"For you, {title}, always.", None
    if re.fullmatch(r"(?:good morning|good afternoon|good evening|hello|hi|hey)", cmd):
        now = datetime.datetime.now()
        return (f"Good {_part_of_day()}, {title}. It's {_clock(now)}. Say briefing for the full report."), None
    if re.fullmatch(r"(?:good night|night night)", cmd):
        return f"Good night, {title}. I'll keep watch.", None

    
    m = re.fullmatch(r"call me ([a-z]{2,15}(?: [a-z]{2,15})?)", cmd)
    if m:
        config.USER_TITLE = m.group(1)
        return f"Very well. From now on, {config.USER_TITLE}.", None

    
    if re.search(r"\b(?:list|what|which|show) (?:your |the |my )?(?:protocols|modes|routines)\b|\bwhat protocols\b", cmd):
        return (f"I have {', '.join(k + ' mode' for k in config.ROUTINES)}, {title}."), None
    m = _ROUTINE_RE.match(cmd)
    if m and m.group(1).strip() in config.ROUTINES:
        return run_routine(m.group(1).strip()), None
    m = re.match(r"^(?:initiate|activate|engage) (?:the )?(.+)$", cmd)      
    if m and m.group(1).strip() in config.ROUTINES:
        return run_routine(m.group(1).strip()), None

    
    reply = _handle_people(cmd, title)
    if reply is not None:
        return reply

    
    m = re.match(r"^(force close|force quit|kill|close|quit|terminate|exit) (?:the |my )?(.+?)(?: app| application| program| window)?$", cmd)
    if m:
        verb, name = m.group(1), m.group(2).strip()
        if name in _VAGUE:
            return f"Which app should I close, {title}?", None
        result = close_app(name, force=verb.startswith(("force", "kill", "terminate")))
        if result == "closed":
            return config.ack(), None
        if result == "notrunning":
            return f"I don't see {name} running, {title}.", None
        if result == "needsforce":
            return f"{name.capitalize()} won't close politely, {title}. Say force close {name}.", None
        if result == "protected":
            return f"I'd rather not close {name}, {title}. Say goodbye if you want me offline.", None
        if result == "unsupported":
            return "I can only close apps on Windows.", None
        return f"I'm not sure what {name} is, {title}.", None

    
    if re.search(r"\bcancel (?:the )?(?:shutdown|restart|reboot)\b|\babort (?:the )?(?:shutdown|restart)\b", cmd):
        if os.name == "nt":
            subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=_NOWIN)
        return f"Shutdown cancelled, {title}.", None
    if re.search(r"\b(?:shut ?down|turn off|power off|power down) (?:the |my )?(?:computer|pc|laptop|system|machine)\b", cmd):
        return _ask_power("shutdown", title), None
    if re.search(r"\b(?:restart|reboot) (?:the |my )?(?:computer|pc|laptop|system|machine)\b", cmd):
        return _ask_power("restart", title), None
    if re.search(r"\b(?:(?:put|send) (?:the |my )?(?:computer|pc|laptop|system) to sleep|sleep (?:the |my )?(?:computer|pc|laptop))\b", cmd):
        return _ask_power("sleep", title), None
    if re.search(r"\bhibernate\b", cmd):
        return _ask_power("hibernate", title), None
    if re.search(r"\b(sign out|log out|log off)\b", cmd):
        return _ask_power("signout", title), None
    if re.search(r"\bempty (?:the |my )?(?:recycle bin|trash|bin)\b", cmd):
        return _ask_power("recyclebin", title), None

    
    if re.search(r"\block (?:the |my )?(?:computer|pc|laptop|screen|workstation|system)\b|\block up\b", cmd):
        if lock_screen():
            return f"Locking up, {title}.", None
        return "I can only lock a Windows PC.", None
    if re.search(r"\bdynamic lock\b", cmd):
        _start(SETTINGS_PAGES["sign in"])
        return config._title_fmt(DYNAMIC_LOCK_REPLY), None
    if (re.search(r"\b(?:set ?up|enable|turn on|add|configure)\b.*\b(?:face|fingerprint|windows hello|biometric|finger print)\b", cmd)
            or re.search(r"\bunlock (?:with|using|by) (?:my |the )?(?:face|fingerprint|finger print)\b", cmd)
            or re.search(r"\b(?:unlock|log in|sign in) without (?:typing|a password|the password)\b", cmd)
            or re.search(r"\bhow (?:do|can|could) i unlock\b", cmd)):
        _start(SETTINGS_PAGES["sign in"])
        return config._title_fmt(HELLO_REPLY), None
    if re.search(r"\b(unlock|log me in|sign me in|let me in)\b", cmd):
        return config._title_fmt(UNLOCK_REPLY), None
    if re.search(r"\b(?:wake (?:up )?(?:the |my )?(?:screen|display|monitor)|turn on (?:the |my )?(?:screen|display|monitor)|screen on|display on)\b", cmd):
        if wake_display():
            return f"Display awake, {title}. If the screen is locked, sign in with your PIN or face.", None
        return "I can only do that on Windows.", None
    if re.search(r"\b(?:turn off|switch off|power off) (?:the |my )?(?:screen|display|monitor)\b|\bscreen off\b|\bdisplay off\b", cmd):
        return _can_do(display_off(), title, "that"), None
    if re.search(r"\b(?:stay awake|keep (?:the |my )?(?:pc|computer|laptop|screen)? ?awake|prevent sleep|caffeine on)\b", cmd):
        return (f"Staying awake, {title}. I'll keep the screen on while I run." if keep_awake(True)
                else "I can only do that on Windows."), None
    if re.search(r"\b(?:stop staying awake|allow sleep|caffeine off|let (?:the |my )?(?:pc|computer|laptop) sleep)\b", cmd):
        return (f"Normal sleep settings restored, {title}." if keep_awake(False)
                else "I can only do that on Windows."), None

    
    if re.search(r"\b(what time is it|whats the time|what is the time|tell me the time|current time)\b", cmd):
        return f"It's {_clock(datetime.datetime.now())}, {title}.", None
    if re.search(r"\b(whats the date|what is the date|whats todays date|what day is it|todays date|tell me the date)\b", cmd):
        now = datetime.datetime.now()
        return f"Today is {now:%A}, {now.day} {now:%B %Y}.", None
    if re.search(r"\bwhat year is it\b", cmd):
        return f"It is {datetime.datetime.now():%Y}, {title}.", None

    
    if re.search(r"\b(system status|status report|diagnostics|system check|how is the system|how are the systems|cpu usage|memory usage|ram usage|disk space)\b", cmd):
        return system_status(title), None
    if re.search(r"\b(briefing|sitrep|brief me|daily brief)\b", cmd):
        return _briefing(memory), None
    if re.search(r"\b(am i online|are we online|is the internet (?:working|up|down)|internet connection|check (?:the )?internet)\b", cmd):
        return (f"We're online, {title}." if is_online() else f"We appear to be offline, {title}."), None
    if re.search(r"\b(?:my ip|ip address)\b", cmd):
        ip = local_ip()
        return (f"This machine's address on your network is {ip.replace('.', ' dot ')}, {title}." if ip
                else f"I can't find a network address, {title}."), None
    if re.search(r"\b(what apps are running|whats running|running apps|list running apps|what do i have open|what is open|whats open)\b", cmd):
        apps = running_apps()
        if apps is None:
            return "I can only list running apps on Windows.", None
        if not apps:
            return f"Nothing much is open, {title}.", None
        return f"You have {len(apps)} open: " + ", ".join(apps[:8]) + ".", None
    if re.search(r"\b(?:read|whats on|what is on|whats in) (?:my |the )?clipboard\b", cmd):
        text = clipboard_text()
        if text is None:
            return "I can only read the clipboard on Windows.", None
        if not text:
            return f"The clipboard is empty, {title}.", None
        return "The clipboard says: " + (text[:250] + ("..." if len(text) > 250 else "")), None

    
    if re.search(r"\b(weather|temperature|forecast)\b", cmd):
        m = re.search(r"\b(?:in|at|for) ([a-z ]+?)(?: today| now| right now| tomorrow| please)*$", cmd)
        city = m.group(1).strip() if m else config.HOME_CITY
        try:
            return weather_report(city), None
        except Exception:
            return f"I can't reach the weather service right now, {title}. Are we online?", None
    if re.search(r"\b(battery|charge level|power level)\b", cmd):
        report = battery_report()
        return (report or f"I can't read the battery on this machine, {title}."), None

    
    m = re.match(r"^(?:what is|whats|calculate|compute|how much is|solve|work out)\s+(.+)$", cmd)
    if m:
        answer = calculate(m.group(1))
        if answer == "divzero":
            return f"That divides by zero, {title}. Even I have limits.", None
        if answer is not None:
            return f"That comes to {answer}, {title}.", None

    
    m = re.search(r"\bvolume (?:to |at )?([a-z0-9 ]+?)(?: percent)?$", cmd)
    if m and to_int(m.group(1)) is not None:
        level = max(0, min(100, to_int(m.group(1))))
        if _press("vol_down", 50):
            _press("vol_up", level // 2)
            return f"Volume set to about {level} percent.", None
        return "I can only change volume on Windows.", None
    if re.search(r"\b(volume up|louder|increase (?:the )?volume|turn (?:it |the volume )?up|raise (?:the )?volume)\b", cmd):
        return _can_do(_press("vol_up", config.VOLUME_STEP), title, "that"), None
    if re.search(r"\b(volume down|quieter|softer|decrease (?:the )?volume|lower (?:the )?volume|turn (?:it |the volume )?down)\b", cmd):
        return _can_do(_press("vol_down", config.VOLUME_STEP), title, "that"), None
    if re.search(r"\b(mute|unmute)\b", cmd):
        return _can_do(_press("mute"), title, "that"), None

    
    m = re.search(r"\bbrightness (?:to |at )?([a-z0-9 ]+?)(?: percent)?$", cmd)
    if m and to_int(m.group(1)) is not None:
        ok = set_brightness(to_int(m.group(1)))
        return (config.ack() if ok else f"I can't change the brightness on this display, {title}."), None
    if re.search(r"\b(brightness up|brighter|increase (?:the )?brightness|raise (?:the )?brightness)\b", cmd):
        cur = get_brightness()
        ok = cur is not None and set_brightness(cur + 20)
        return (config.ack() if ok else f"I can't change the brightness on this display, {title}."), None
    if re.search(r"\b(brightness down|dim|dimmer|decrease (?:the )?brightness|lower (?:the )?brightness)\b", cmd):
        cur = get_brightness()
        ok = cur is not None and set_brightness(cur - 20)
        return (config.ack() if ok else f"I can't change the brightness on this display, {title}."), None

    
    if re.search(r"\b(pause|resume|play pause|pause (?:the )?(?:music|video|song))\b", cmd) and not cmd.startswith("play "):
        _press("play_pause")
        return config.ack(), None
    if re.search(r"\b(next song|next track|skip (?:this )?(?:song|track))\b", cmd):
        _press("next")
        return config.ack(), None
    if re.search(r"\b(previous song|previous track|last song|go back a song)\b", cmd):
        _press("prev")
        return config.ack(), None

    
    if re.search(r"\b(show (?:the )?desktop|minimi[sz]e (?:all|everything|all windows))\b", cmd):
        return _can_do(_hotkey("win", "d"), title), None
    if re.search(r"\b(switch (?:window|windows|app|apps)|next window|alt tab)\b", cmd):
        return _can_do(_hotkey("alt", "tab"), title), None
    if re.search(r"\bmaximi[sz]e (?:this |the )?(?:window)?$", cmd):
        return _can_do(_hotkey("win", "up"), title), None
    if re.search(r"\bminimi[sz]e (?:this |the )?(?:window)?$", cmd):
        return _can_do(_hotkey("win", "down"), title), None

    
    if re.search(r"\b(screenshot|screen shot|capture (?:the |my )?screen)\b", cmd):
        return take_screenshot(title), None

    
    m = re.search(r"\bremind me in (.+?) " + _UNIT_RE + r"\b(?: to (.+))?$", cmd)
    if m and to_int(m.group(1)) is not None:
        amount, unit, what = to_int(m.group(1)), m.group(2), m.group(3)
        _add_alarm(_seconds(amount, unit),
                   f"Reminder, {title}: {what}." if what else f"Your reminder is up, {title}.")
        return f"I'll remind you in {_duration_text(amount, unit)}.", None
    m = re.match(r"^(?:set (?:an |a )?alarm|wake me(?: up)?)(?: for| at) (\d{1,2})(?: (\d{2}))?(?: ?(a m|p m|am|pm))?(?: (?:to|for) (.+))?$", cmd)
    if m:
        target = next_clock_time(int(m.group(1)), int(m.group(2) or 0), m.group(3) or "")
        if target is None:
            return f"That isn't a time I recognise, {title}.", None
        what = m.group(4)
        _add_alarm((target - datetime.datetime.now()).total_seconds(),
                   f"Alarm, {title}: {what}." if what else f"Your alarm is ringing, {title}.")
        day = "" if target.date() == datetime.date.today() else " tomorrow"
        return f"Alarm set for {_clock(target)}{day}, {title}.", None
    m = re.search(r"\btimer (?:for )?(.+?) " + _UNIT_RE + r"\b", cmd)       
    amount = to_int(m.group(1)) if m else None
    if amount is None:
        m = re.search(r"\b(.+?) " + _UNIT_RE + r" timer\b", cmd)            
        amount = _number_at_end(m.group(1)) if m else None
    if m and amount is not None:
        unit = m.group(2)
        _add_alarm(_seconds(amount, unit), f"Your timer is up, {title}.")
        return f"Timer set for {_duration_text(amount, unit)}.", None

    
    m = re.match(r"^(?:take a note|make a note|write down|jot down|note down)(?: that)? (.+)$", cmd)
    if m:
        try:
            with open(config.NOTES_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] {m.group(1)}\n")
            return f"Noted in your notes file, {title}.", None
        except OSError as e:
            return f"I couldn't write the note, {title}: {e}", None
    if re.fullmatch(r"(?:open|show) (?:the |my )?notes? file", cmd):
        if os.path.exists(config.NOTES_FILE) and _start(config.NOTES_FILE):
            return config.ack(), None
        return f"You haven't taken any notes yet, {title}.", None
    if re.search(r"\b(what did i ask you to remember|read my notes|what are my notes|what do you remember|my notes)\b", cmd):
        if not memory.notes:
            return f"You haven't asked me to remember anything, {title}.", None
        return "You asked me to remember: " + ". ".join(memory.notes[-5:]) + ".", None
    if re.search(r"\b(forget everything|clear your memory|clear memory|reset your memory|reset memory)\b", cmd):
        memory.clear()
        return f"Memory wiped, {title}.", None
    m = re.match(r"^remember (?:that )?(.+)$", cmd)
    if m:
        memory.add_note(m.group(1))
        return f"Noted, {title}.", None

    
    if re.search(r"\b(flip a coin|toss a coin|heads or tails)\b", cmd):
        return f"{random.choice(['Heads', 'Tails'])}, {title}.", None
    if re.search(r"\b(roll a dice|roll a die|roll the dice|throw a dice)\b", cmd):
        return f"You rolled a {random.randint(1, 6)}, {title}.", None
    m = re.search(r"\b(?:pick|choose|give me) a (?:random )?number (?:between|from) (\d+) (?:and|to) (\d+)\b", cmd)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return f"{random.randint(lo, hi)}, {title}.", None

    
    if re.search(r"\b(what can you do|help me|your commands|list commands)\b", cmd):
        return ("I can open and close apps, websites, folders and projects, lock the screen, run protocols like "
                "work mode, WhatsApp or call your contacts and tell you about them, check weather, battery and "
                "system health, set timers and alarms, take screenshots, control volume, brightness and music, "
                "do sums, take notes, shut down or restart with your confirmation, and chat about anything, "
                f"{title}."), None

    
    m = re.match(r"^(?:search|google|look up)(?: for)? (.+)$", cmd)
    if m:
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(m.group(1)))
        return f"Searching for {m.group(1)}.", None
    m = re.match(r"^play (.+?)(?: on youtube)?$", cmd)
    if m:
        webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(m.group(1)))
        return f"Pulling up {m.group(1)} on YouTube.", None

    
    m = re.match(r"^open (?:the |my )?(?:project )?(.+?) (?:project )?in (?:vs code|vscode|visual studio code|code)$", cmd)
    if m:
        name = m.group(1).strip()
        path = config.PROJECTS.get(name)
        if not path:
            return f"I don't know a project called {name}, {title}. Add it to config.py.", None
        try:
            subprocess.Popen(f'code "{path}"', shell=True)
            return f"Opening {name} in VS Code.", None
        except OSError:
            return f"I could not start VS Code, {title}.", None

    
    m = re.match(r"^open (?:the |my )?(.+?) settings$", cmd)
    if m and m.group(1).strip() in SETTINGS_PAGES:
        if _start(SETTINGS_PAGES[m.group(1).strip()]):
            return f"Opening {m.group(1).strip()} settings, {title}.", None
        return "I can only open settings pages on Windows.", None

    
    m = re.match(r"^(?:open|launch|start) (?:the |my )?(.+)$", cmd)
    if m:
        name = m.group(1).strip()
        is_project = False
        for suffix in (" folder", " directory", " app", " application", " website", " site"):
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
        if name.startswith("project "):
            name, is_project = name[len("project "):].strip(), True
        elif name.endswith(" project"):
            name, is_project = name[: -len(" project")].strip(), True

        kind = open_target(name, is_project)
        if kind == "folder":
            return f"Opening your {name} folder.", None
        if kind == "project":
            return f"Opening the {name} project folder.", None
        if kind:
            return f"Opening {name}, {title}.", None
        if name in APPS:
            return f"I tried, {title}, but I could not open {name}.", None
        return f"I couldn't find {name} on this machine, {title}.", None

    
    return knowledge.answer(cmd)
