"""Live knowledge: Wikipedia, news, world time, currency, country facts.

Nothing here is "trained in". Friday looks the answer up when you ask, so it is current and
works for almost any topic. It needs internet and sends only the topic you asked about.

    "who is Albert Einstein"          "what is photosynthesis"       "tell me about the Taj Mahal"
    "what is the news"                "what time is it in Tokyo"     "convert 100 dollars to rupees"
    "capital of France"               "population of Japan"
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import config

_UA = {"User-Agent": "FridayAssistant/1.0 (personal voice assistant)"}


class Offline(Exception):
    pass


def _get(url: str):
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=config.NET_TIMEOUT_S) as r:
            return r.read()
    except urllib.error.HTTPError:
        return None                       # 404 etc: the page simply does not exist
    except Exception as e:                # no internet, DNS, timeout
        raise Offline(str(e))


def _json(url: str):
    raw = _get(url)
    return json.loads(raw.decode("utf-8")) if raw else None


# ----- Wikipedia ------------------------------------------------------------
def _clean(text: str) -> str:
    text = re.sub(r"\s*\([^()]*\)", "", text)              # (born 1879 ...), (pronunciation)
    text = re.sub(r"\s*\[[^\]]*\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str, n: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", _clean(text))
    out = " ".join(parts[:n])
    return out if len(out) <= 520 else out[:520].rsplit(" ", 1)[0] + "."


def wiki(topic: str, code: str = "en"):
    """Short spoken summary of a Wikipedia article, or None when there is none."""
    q = urllib.parse.quote(topic)
    search = _json(f"https://{code}.wikipedia.org/w/api.php?action=opensearch&search={q}&limit=4&format=json")
    titles = search[1] if search and len(search) > 1 else []
    for title in titles:
        data = _json(f"https://{code}.wikipedia.org/api/rest_v1/page/summary/"
                     + urllib.parse.quote(title.replace(" ", "_"), safe=""))
        if not data or data.get("type") == "disambiguation":
            continue
        extract = data.get("extract") or ""
        if extract:
            return _sentences(extract, config.WIKI_SENTENCES)
    return None


# ----- time in other cities ---------------------------------------------------
TZ = {
    "delhi": "Asia/Kolkata", "new delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "kolkata": "Asia/Kolkata",
    "india": "Asia/Kolkata", "pune": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "bengaluru": "Asia/Kolkata",
    "chennai": "Asia/Kolkata", "hyderabad": "Asia/Kolkata", "nagpur": "Asia/Kolkata", "jaipur": "Asia/Kolkata",
    "london": "Europe/London", "uk": "Europe/London", "england": "Europe/London", "paris": "Europe/Paris",
    "france": "Europe/Paris", "berlin": "Europe/Berlin", "germany": "Europe/Berlin", "rome": "Europe/Rome",
    "italy": "Europe/Rome", "madrid": "Europe/Madrid", "spain": "Europe/Madrid", "amsterdam": "Europe/Amsterdam",
    "zurich": "Europe/Zurich", "moscow": "Europe/Moscow", "russia": "Europe/Moscow", "istanbul": "Europe/Istanbul",
    "turkey": "Europe/Istanbul", "dubai": "Asia/Dubai", "abu dhabi": "Asia/Dubai", "uae": "Asia/Dubai",
    "doha": "Asia/Qatar", "qatar": "Asia/Qatar", "riyadh": "Asia/Riyadh", "saudi arabia": "Asia/Riyadh",
    "kuwait": "Asia/Kuwait", "tehran": "Asia/Tehran", "kabul": "Asia/Kabul", "karachi": "Asia/Karachi",
    "pakistan": "Asia/Karachi", "lahore": "Asia/Karachi", "dhaka": "Asia/Dhaka", "bangladesh": "Asia/Dhaka",
    "kathmandu": "Asia/Kathmandu", "nepal": "Asia/Kathmandu", "colombo": "Asia/Colombo",
    "sri lanka": "Asia/Colombo", "bangkok": "Asia/Bangkok", "thailand": "Asia/Bangkok",
    "jakarta": "Asia/Jakarta", "singapore": "Asia/Singapore", "kuala lumpur": "Asia/Kuala_Lumpur",
    "malaysia": "Asia/Kuala_Lumpur", "manila": "Asia/Manila", "hong kong": "Asia/Hong_Kong",
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai", "china": "Asia/Shanghai", "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo", "seoul": "Asia/Seoul", "korea": "Asia/Seoul", "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne", "australia": "Australia/Sydney", "auckland": "Pacific/Auckland",
    "new zealand": "Pacific/Auckland", "cairo": "Africa/Cairo", "egypt": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg", "south africa": "Africa/Johannesburg", "lagos": "Africa/Lagos",
    "nairobi": "Africa/Nairobi", "new york": "America/New_York", "washington": "America/New_York",
    "boston": "America/New_York", "miami": "America/New_York", "toronto": "America/Toronto",
    "chicago": "America/Chicago", "texas": "America/Chicago", "dallas": "America/Chicago",
    "denver": "America/Denver", "los angeles": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "seattle": "America/Los_Angeles", "california": "America/Los_Angeles", "vancouver": "America/Vancouver",
    "usa": "America/New_York", "america": "America/New_York", "us": "America/New_York",
    "mexico city": "America/Mexico_City", "sao paulo": "America/Sao_Paulo", "brazil": "America/Sao_Paulo",
    "buenos aires": "America/Argentina/Buenos_Aires", "honolulu": "Pacific/Honolulu", "hawaii": "Pacific/Honolulu",
    "utc": "UTC", "gmt": "UTC",
}


def world_time(place: str):
    place = place.strip().lower()
    zone = TZ.get(place)
    if not zone:
        return None
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(zone))
    except Exception:
        return f"I need the tzdata package for that, {config.USER_TITLE}. Run: pip install tzdata"
    local = datetime.now().astimezone()
    diff = (now.utcoffset() - local.utcoffset()).total_seconds() / 3600
    when = now.strftime("%I:%M %p").lstrip("0")
    day = now.strftime("%A")
    rel = "the same time as here" if abs(diff) < 0.01 else (
        f"{abs(diff):g} hours {'ahead of' if diff > 0 else 'behind'} you")
    return f"It is {when} on {day} in {place.title()}, {config.USER_TITLE}, {rel}."


# ----- currency ---------------------------------------------------------------
CUR = {
    "usd": "USD", "dollar": "USD", "dollars": "USD", "us dollar": "USD", "us dollars": "USD",
    "inr": "INR", "rupee": "INR", "rupees": "INR", "indian rupee": "INR", "indian rupees": "INR",
    "eur": "EUR", "euro": "EUR", "euros": "EUR", "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
    "jpy": "JPY", "yen": "JPY", "aed": "AED", "dirham": "AED", "dirhams": "AED", "cny": "CNY",
    "yuan": "CNY", "cad": "CAD", "canadian dollar": "CAD", "canadian dollars": "CAD", "aud": "AUD",
    "australian dollar": "AUD", "australian dollars": "AUD", "chf": "CHF", "franc": "CHF", "francs": "CHF",
    "sgd": "SGD", "singapore dollar": "SGD", "singapore dollars": "SGD", "sar": "SAR", "riyal": "SAR",
    "riyals": "SAR", "pkr": "PKR", "bdt": "BDT", "taka": "BDT", "lkr": "LKR", "npr": "NPR",
    "rub": "RUB", "ruble": "RUB", "rubles": "RUB", "krw": "KRW", "won": "KRW", "thb": "THB", "baht": "THB",
}
CUR_NAME = {"USD": "US dollars", "INR": "Indian rupees", "EUR": "euros", "GBP": "pounds", "JPY": "yen",
            "AED": "dirhams", "CNY": "yuan", "CAD": "Canadian dollars", "AUD": "Australian dollars",
            "CHF": "Swiss francs", "SGD": "Singapore dollars", "SAR": "riyals", "PKR": "Pakistani rupees",
            "BDT": "taka", "LKR": "Sri Lankan rupees", "NPR": "Nepali rupees", "RUB": "rubles",
            "KRW": "won", "THB": "baht"}
_CUR_KEYS = "|".join(sorted((re.escape(k) for k in CUR), key=len, reverse=True))
_CONVERT = re.compile(
    r"^(?:convert |how much is |what is |whats |how many )?([0-9]+(?: [0-9]+)?(?:\.[0-9]+)?|a|one|an) "
    r"(" + _CUR_KEYS + r")(?: is| are)? (?:to|in|into) (" + _CUR_KEYS + r")(?: is that| please)?$")


def convert_currency(amount: float, src: str, dst: str):
    data = _json(f"https://open.er-api.com/v6/latest/{src}")
    rate = (data or {}).get("rates", {}).get(dst)
    if not rate:
        return None
    value = amount * rate
    shown = f"{value:,.0f}" if value >= 100 else f"{value:,.2f}"
    amt = f"{amount:g}"
    return f"{amt} {CUR_NAME.get(src, src)} is about {shown} {CUR_NAME.get(dst, dst)}, {config.USER_TITLE}."


# ----- countries --------------------------------------------------------------
def country_fact(kind: str, name: str):
    q = urllib.parse.quote(name)
    data = _json(f"https://restcountries.com/v3.1/name/{q}?fields=name,capital,population,currencies,languages,area")
    if not data:
        return None
    pick = next((c for c in data if c["name"]["common"].lower() == name.lower()), data[0])
    cn, t = pick["name"]["common"], config.USER_TITLE
    if kind == "capital" and pick.get("capital"):
        return f"The capital of {cn} is {pick['capital'][0]}, {t}."
    if kind == "population":
        return f"{cn} has about {pick['population']:,} people, {t}."
    if kind == "currency" and pick.get("currencies"):
        cur = list(pick["currencies"].values())[0]
        return f"The currency of {cn} is the {cur['name']}, {t}."
    if kind in ("language", "languages") and pick.get("languages"):
        return f"People in {cn} speak {', '.join(pick['languages'].values())}, {t}."
    if kind == "area" and pick.get("area"):
        return f"{cn} covers about {pick['area']:,.0f} square kilometres, {t}."
    return None


# ----- news -------------------------------------------------------------------
def news():
    region = config.NEWS_REGION.upper()
    url = f"https://news.google.com/rss?hl=en-{region}&gl={region}&ceid={region}:en"
    raw = _get(url)
    if not raw:
        return None
    root = ET.fromstring(raw)
    titles = []
    for item in root.iter("item"):
        title = re.sub(r"\s+-\s+[^-]+$", "", (item.findtext("title") or "").strip())   # drop " - Source"
        if title:
            titles.append(title)
        if len(titles) >= config.NEWS_ITEMS:
            break
    return titles or None


# ----- the router -------------------------------------------------------------
_PRON = {"it", "this", "that", "he", "she", "they", "them", "him", "her", "me", "you", "i", "we", "there", "here",
         "what", "who", "mine", "yours", "something", "anything", "everything", "up", "good", "next", "time", "date"}

_PERSONAL = {"my", "your", "our", "his", "her", "their", "you", "i", "we", "it", "he", "she", "they", "me"}
_MATHY = re.compile(r"\b(?:percent|plus|minus|times|divided|squared|cubed|power|multiplied|root of|sum of)\b")

_WIKI_EN = re.compile(
    r"^(?:who (?:is|was|were|are) |what (?:is|was|are|were) |what do you know about |tell me about |"
    r"tell me something about |explain |define |describe |wikipedia |search wikipedia for |"
    r"look up |lookup |give me information about |give me info on |information about |information on )"
    r"(?:a |an |the )?(.+)$")

_NEWS_EN = re.compile(r"^(?:what(?:s| is) the news|whats new in the world|latest news|news headlines|headlines|"
                      r"top headlines|top news|read (?:me )?the news|read (?:me )?the headlines|any news|"
                      r"tell me the news|give me the news|news today|today news|news)$")
_TIME_IN = re.compile(r"^(?:what(?:s| is) the time in |what time is it in |time in |current time in |"
                      r"tell me the time in )(.+?)(?: right now| now)?$")
_COUNTRY = re.compile(r"^(?:what(?:s| is) |tell me )?(?:the )?(capital|population|currency|languages?|area|size) of (.+)$")

_NUMWORD = {"a": 1, "an": 1, "one": 1}


def _spoken_number(s: str):
    s = s.strip()
    if s in _NUMWORD:
        return float(_NUMWORD[s])
    try:
        return float(s.replace(" ", ""))
    except ValueError:
        return None


def _offline() -> str:
    return f"I cannot reach the internet, {config.USER_TITLE}."


def answer(cmd: str):
    """(reply, None) if this is a lookup question, else None so the AI model can take it."""
    if not config.ONLINE_KNOWLEDGE:
        return None
    c = cmd.strip()
    if not c:
        return None
    t = config.USER_TITLE
    try:
        # world time
        m = _TIME_IN.match(c)
        if m:
            r = world_time(m.group(1))
            if r:
                return r, None
        # currency
        m = _CONVERT.match(c)
        if m:
            amount = _spoken_number(m.group(1))
            if amount is not None:
                r = convert_currency(amount, CUR[m.group(2)], CUR[m.group(3)])
                if r:
                    return r, None
        # country facts
        m = _COUNTRY.match(c)
        if m:
            kind = "area" if m.group(1) == "size" else m.group(1)
            try:
                r = country_fact(kind, m.group(2).strip())
            except Offline:
                return None                       # offline: let the AI model answer from memory
            if r:
                return r, None
        # news
        if _NEWS_EN.match(c):
            items = news()
            if not items:
                return None
            return f"Here are the top headlines, {t}. " + " ... ".join(i.rstrip(".") + "." for i in items), None
        # Wikipedia
        m = _WIKI_EN.match(c)
        topic = m.group(1).strip() if m else None
        if topic:
            topic = re.sub(r"\s+(?:to me|for me|please|sir)$", "", topic).strip()
            words = topic.split()
            if not words or (topic in _PRON or words[0] in _PERSONAL):
                return None
            if len(words) > 8 or topic[0].isdigit() or _MATHY.search(topic):
                return None                         # sums and long chatty questions are for the AI model
            try:
                summary = wiki(topic)
            except Offline:
                return None                         # offline: let the AI model answer from memory
            if summary:
                return summary, None
    except Offline:
        return _offline(), None
    except Exception:
        return None
    return None
