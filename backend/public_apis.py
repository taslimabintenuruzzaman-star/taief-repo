"""Live tools drawn from public-apis/public-apis (no API key required)."""

from __future__ import annotations

import asyncio
import base64
import re
from typing import Any
from urllib.parse import quote

import httpx

SOURCE = "https://github.com/public-apis/public-apis"
GITHUB_README = "https://api.github.com/repos/public-apis/public-apis/contents/README.md"

HEADERS = {
    "User-Agent": "MOROS-AGI/1.1 (Jarvis HUD; +https://github.com/public-apis/public-apis)",
    "Accept": "application/json, text/plain;q=0.9",
}

CATALOG: list[dict[str, str]] = [
    {"name": "Open-Meteo", "auth": "No", "use": "weather", "url": "https://open-meteo.com"},
    {"name": "CoinGecko", "auth": "No", "use": "crypto", "url": "https://www.coingecko.com/en/api"},
    {"name": "ExchangeRate-API", "auth": "No", "use": "fx", "url": "https://www.exchangerate-api.com"},
    {"name": "REST Countries", "auth": "No", "use": "country", "url": "https://restcountries.com"},
    {"name": "Free Dictionary", "auth": "No", "use": "define", "url": "https://dictionaryapi.dev"},
    {"name": "Wikipedia", "auth": "No", "use": "wiki", "url": "https://www.mediawiki.org/wiki/REST_API"},
    {"name": "JokeAPI", "auth": "No", "use": "joke", "url": "https://jokeapi.dev"},
    {"name": "Advice Slip", "auth": "No", "use": "advice", "url": "https://api.adviceslip.com"},
    {"name": "ZenQuotes", "auth": "No", "use": "quote", "url": "https://zenquotes.io"},
    {"name": "Cat Facts", "auth": "No", "use": "cat", "url": "https://catfact.ninja"},
    {"name": "Dog CEO", "auth": "No", "use": "dog", "url": "https://dog.ceo/dog-api"},
    {"name": "Numbers API", "auth": "No", "use": "trivia", "url": "http://numbersapi.com"},
    {"name": "Spaceflight News", "auth": "No", "use": "news", "url": "https://spaceflightnewsapi.net"},
    {"name": "NASA APOD", "auth": "No (DEMO_KEY)", "use": "nasa", "url": "https://api.nasa.gov"},
    {"name": "Aladhan", "auth": "No", "use": "prayer", "url": "https://aladhan.com/prayer-times-api"},
]

COINS = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "sol": "solana",
    "solana": "solana",
    "doge": "dogecoin",
    "dogecoin": "dogecoin",
}

_FX = {"BDT": 122.4, "INR": 88.1, "EUR": 0.86, "GBP": 0.74, "JPY": 147.2, "AUD": 1.52, "CAD": 1.37, "USD": 1.0}

_COUNTRIES = {
    "bangladesh": ("Bangladesh", "Asia", "Dhaka", 173000000),
    "india": ("India", "Asia", "New Delhi", 1428000000),
    "japan": ("Japan", "Asia", "Tokyo", 124000000),
    "united states": ("United States", "Americas", "Washington, D.C.", 333000000),
    "usa": ("United States", "Americas", "Washington, D.C.", 333000000),
    "uk": ("United Kingdom", "Europe", "London", 67000000),
}

_DEFS = {
    "gravity": "the force that attracts a body toward the centre of the earth, or toward any other physical body having mass.",
    "api": "a set of functions and procedures allowing the creation of applications that access the features or data of an operating system, application, or other service.",
    "agi": "artificial general intelligence: a hypothetical AI that can understand, learn, and apply knowledge across domains at a human-like level.",
    "jarvis": "fictional AI assistant created by Tony Stark in the Marvel universe; Just A Rather Very Intelligent System.",
}

_WIKI = {
    "jarvis": "J.A.R.V.I.S. is a fictional artificial intelligence in Marvel comics and films, created by Tony Stark as a house system that later evolves into a combat and engineering partner.",
    "dhaka": "Dhaka is the capital and largest city of Bangladesh, on the Buriganga River, and the economic, political, and cultural centre of the country.",
    "bangladesh": "Bangladesh is a country in South Asia, with Dhaka as its capital, known for the Ganges–Brahmaputra delta, dense population, and Bengali language.",
    "iron man": "Iron Man is a Marvel superhero, the armored identity of inventor Tony Stark, first appearing in Tales of Suspense in 1963.",
    "nasa": "NASA is the United States civilian space agency, responsible for aeronautics research, human spaceflight, and robotic exploration of the solar system.",
    "bitcoin": "Bitcoin is a decentralized digital currency created in 2009, secured by proof-of-work and recorded on a public blockchain.",
}

_ROW = re.compile(
    r"^\| \[([^\]]+)\]\(([^)]+)\) \| ([^|]+) \| ([^|]+) \|",
    re.M,
)


async def _request(url: str, params: dict | None, verify: bool) -> Any:
    async with httpx.AsyncClient(
        timeout=8.0, headers=HEADERS, follow_redirects=True, verify=verify
    ) as client:
        res = await client.get(url, params=params)
        res.raise_for_status()
        ctype = res.headers.get("content-type", "")
        if "application/json" in ctype:
            return res.json()
        try:
            return res.json()
        except Exception:
            return {"text": res.text.strip()}


async def get_json(url: str, params: dict | None = None, fallback: Any = None) -> Any:
    try:
        return await _request(url, params, True)
    except Exception:
        try:
            return await _request(url, params, False)
        except Exception:
            if fallback is not None:
                return fallback
            raise


def _ok(name: str, spoken: str, cached: bool = False, **extra) -> dict:
    extra.update({"source": name, "catalog": SOURCE, "spoken": spoken, "cached": cached})
    return extra


def parse_public_apis_readme(markdown: str) -> dict[str, Any]:
    no_auth: list[dict[str, str]] = []
    for match in _ROW.finditer(markdown):
        name, url, desc, auth = (p.strip() for p in match.groups())
        if auth.lower() == "no":
            no_auth.append({"name": name, "url": url, "description": desc, "auth": "No"})
    return {
        "source": SOURCE,
        "total_rows": len(_ROW.findall(markdown)),
        "no_auth": len(no_auth),
        "wired": CATALOG,
        "sample": no_auth[:40],
    }


async def github_catalog() -> dict[str, Any]:
    data = await get_json(GITHUB_README)
    md = base64.b64decode(data["content"]).decode("utf-8")
    parsed = parse_public_apis_readme(md)
    parsed["live"] = True
    return parsed


async def crypto_prices(ids: list[str] | None = None) -> dict:
    wanted = ids or ["bitcoin", "ethereum"]
    fallback = {coin: {"usd": {"bitcoin": 97450, "ethereum": 4280, "solana": 210, "dogecoin": 0.18}.get(coin, 1)} for coin in wanted}
    data = await get_json(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids": ",".join(wanted), "vs_currencies": "usd"},
        fallback=fallback,
    )
    cached = data == fallback
    parts = [f"{coin} {info.get('usd')} US dollars" for coin, info in data.items()]
    spoken = "Market feed: " + "; ".join(parts) + "."
    if cached:
        spoken += " CoinGecko is cached on this node."
    return _ok("CoinGecko", spoken, cached=cached, prices=data)


async def fx_usd() -> dict:
    fallback = {"rates": _FX}
    data = await get_json("https://open.er-api.com/v6/latest/USD", fallback=fallback)
    rates = data.get("rates") or _FX
    bdt, inr, eur = rates.get("BDT"), rates.get("INR"), rates.get("EUR")
    spoken = f"One US dollar buys {bdt} Bangladeshi taka, {inr} Indian rupees, and {eur} euro."
    return _ok("ExchangeRate-API", spoken, cached=data is fallback, usd_bdt=bdt, usd_inr=inr, usd_eur=eur)


async def convert_fx(amount: float, src: str, dst: str) -> dict:
    src, dst = src.upper(), dst.upper()
    fallback = {"rates": {**_FX, src: 1.0}}
    data = await get_json(f"https://open.er-api.com/v6/latest/{src}", fallback=fallback)
    rates = data.get("rates") or {}
    if dst not in rates and src == "USD" and dst in _FX:
        rates = {**_FX, **rates}
    if src != "USD" and dst not in rates:
        usd_src = _FX.get(src)
        usd_dst = _FX.get(dst)
        if usd_src and usd_dst:
            rate = usd_dst / usd_src
            value = round(amount * rate, 4)
            spoken = f"{amount} {src} is {value} {dst} at the cached mid-market rate."
            return _ok("ExchangeRate-API", spoken, cached=True, amount=amount, from_ccy=src, to_ccy=dst, value=value)
    rate = rates.get(dst)
    if rate is None:
        raise ValueError("unknown currency")
    value = round(amount * float(rate), 4)
    spoken = f"{amount} {src} is {value} {dst} at the live mid-market rate."
    return _ok("ExchangeRate-API", spoken, cached=data is fallback, amount=amount, from_ccy=src, to_ccy=dst, value=value)


async def country_info(name: str) -> dict:
    key = name.strip().lower()
    fb = None
    if key in _COUNTRIES:
        common, region, capital, pop = _COUNTRIES[key]
        fb = [{"name": {"common": common}, "region": region, "capital": [capital], "population": pop}]
    data = await get_json(f"https://restcountries.com/v3.1/name/{quote(name)}", fallback=fb)
    if not data:
        raise ValueError("unknown country")
    c = data[0]
    capital = (c.get("capital") or ["unknown"])[0]
    pop = c.get("population")
    region = c.get("region")
    spoken = f"{c['name']['common']} is in {region}, capital {capital}, population about {pop:,}."
    return _ok("REST Countries", spoken, cached=data is fb, country=c["name"]["common"], capital=capital, population=pop)


async def define_word(word: str) -> dict:
    key = word.strip().lower()
    fb = None
    if key in _DEFS:
        fb = [{"word": word, "phonetic": "", "meanings": [{"definitions": [{"definition": _DEFS[key]}]}]}]
    data = await get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}", fallback=fb)
    if not data:
        raise ValueError("unknown word")
    entry = data[0]
    meaning = entry["meanings"][0]["definitions"][0]["definition"]
    phonetic = entry.get("phonetic") or ""
    spoken = f"{entry['word']}{': ' + phonetic if phonetic else ''}. {meaning}"
    return _ok("Free Dictionary API", spoken, cached=data is fb, word=entry["word"], definition=meaning)


async def wiki_summary(topic: str) -> dict:
    key = topic.strip().lower()
    title = quote(topic.strip().replace(" ", "_"))
    fb = {"title": topic, "extract": _WIKI.get(key, ""), "thumbnail": {}}
    data = await get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}", fallback=fb if fb["extract"] else None)
    extract = (data.get("extract") or "").split(". ")
    spoken = ". ".join(extract[:2]).strip()
    if spoken and not spoken.endswith("."):
        spoken += "."
    if not spoken:
        spoken = f"No Wikipedia card cached for {topic}. Try another subject."
    image = (data.get("thumbnail") or {}).get("source")
    return _ok("Wikipedia", spoken, cached=data is fb, title=data.get("title"), image=image)


async def random_joke() -> dict:
    fb = {"joke": "There are only 10 kinds of people: those who understand binary and those who do not."}
    data = await get_json("https://v2.jokeapi.dev/joke/Programming,Pun?safe-mode&type=single", fallback=fb)
    joke = data.get("joke") or fb["joke"]
    return _ok("JokeAPI", joke, cached=data is fb, joke=joke)


async def advice() -> dict:
    fb = {"slip": {"advice": "Keep the interface simple; complexity belongs in the engine."}}
    data = await get_json("https://api.adviceslip.com/advice", fallback=fb)
    line = data.get("slip", {}).get("advice") or fb["slip"]["advice"]
    return _ok("Advice Slip", f"Counsel: {line}", cached=data is fb, advice=line)


async def random_quote() -> dict:
    fb = [{"q": "placeholder", "a": "MOROS"}]
    data = await get_json("https://zenquotes.io/api/random", fallback=fb)
    if data is not fb:
        item = data[0] if isinstance(data, list) else data
        q, a = item.get("q"), item.get("a")
        return _ok("ZenQuotes", f"{q} — {a}.", quote=q, author=a)
    try:
        async with httpx.AsyncClient(timeout=6.0, headers=HEADERS, verify=False) as client:
            res = await client.get("https://api.github.com/zen")
            res.raise_for_status()
            q = res.text.strip()
        return _ok("GitHub Zen", f"{q} — GitHub.", quote=q, author="GitHub")
    except Exception:
        q = "The universe is under no obligation to make sense to you."
        return _ok("ZenQuotes", f"{q} — Neil deGrasse Tyson.", cached=True, quote=q, author="Neil deGrasse Tyson")


async def cat_fact() -> dict:
    fb = {"fact": "A group of cats is called a clowder."}
    data = await get_json("https://catfact.ninja/fact", fallback=fb)
    fact = data.get("fact") or fb["fact"]
    return _ok("Cat Facts", fact, cached=data is fb, fact=fact)


async def dog_image() -> dict:
    fb = {"message": "https://images.dog.ceo/breeds/hound-afghan/n02088094_1003.jpg"}
    data = await get_json("https://dog.ceo/api/breeds/image/random", fallback=fb)
    url = data.get("message")
    return _ok("Dog CEO", "A good boy has been acquired. Image on the deck.", cached=data is fb, image=url)


async def number_trivia() -> dict:
    fb = {"text": "42 is the number of laws of cricket."}
    data = await get_json("http://numbersapi.com/random/trivia?json", fallback=fb)
    text = data.get("text") or fb["text"]
    return _ok("Numbers API", text, cached=data is fb, fact=text)


async def space_news() -> dict:
    fb = {
        "results": [
            {"title": "NASA prepares next deep-space logistics window"},
            {"title": "CubeSat swarm completes formation-flying trial"},
            {"title": "Lunar south pole mapping pass returns high-res elevation"},
        ]
    }
    data = await get_json("https://api.spaceflightnewsapi.net/v4/articles/", {"limit": "3"}, fallback=fb)
    results = data.get("results") or []
    headlines = [a.get("title") for a in results if a.get("title")]
    spoken = "Spaceflight headlines: " + "; ".join(headlines[:3]) + "."
    return _ok("Spaceflight News", spoken, cached=data is fb, headlines=headlines)


async def nasa_apod() -> dict:
    fb = {
        "title": "The Pillars of Creation",
        "explanation": "A Hubble icon: interstellar gas and dust in the Eagle Nebula, sculpted by young stars.",
        "url": "https://apod.nasa.gov/apod/image/2207/Pillars_HubbleSchmid_960.jpg",
        "media_type": "image",
    }
    data = await get_json("https://api.nasa.gov/planetary/apod", {"api_key": "DEMO_KEY"}, fallback=fb)
    title = data.get("title")
    blurb = (data.get("explanation") or "")[:280]
    spoken = f"NASA astronomy picture: {title}. {blurb}"
    return _ok("NASA APOD", spoken, cached=data is fb, title=title, image=data.get("url"), media=data.get("media_type"))


async def prayer_dhaka() -> dict:
    fb = {
        "data": {
            "timings": {"Fajr": "04:22", "Dhuhr": "12:00", "Asr": "15:28", "Maghrib": "18:16", "Isha": "19:31"}
        }
    }
    data = await get_json(
        "https://api.aladhan.com/v1/timingsByCity",
        {"city": "Dhaka", "country": "Bangladesh", "method": "1"},
        fallback=fb,
    )
    timings = (data.get("data") or {}).get("timings") or {}
    keys = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")
    parts = [f"{k} {timings.get(k)}" for k in keys]
    spoken = "Dhaka prayer times today: " + ", ".join(parts) + "."
    return _ok("Aladhan", spoken, cached=data is fb, timings={k: timings.get(k) for k in keys})


async def dashboard_feeds() -> dict:
    tasks = {
        "crypto": crypto_prices(),
        "fx": fx_usd(),
        "quote": random_quote(),
        "prayer": prayer_dhaka(),
    }
    keys = list(tasks)
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    out: dict[str, Any] = {"catalog": SOURCE}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            out[key] = {"error": str(result)}
        else:
            out[key] = result
    return out


def detect_coin(text: str) -> str | None:
    for key, coin in COINS.items():
        if re.search(rf"\b{key}\b", text, re.I):
            return coin
    return None


_CCY = {
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "bdt": "BDT",
    "taka": "BDT",
    "jpy": "JPY",
    "yen": "JPY",
    "aud": "AUD",
    "cad": "CAD",
}


def detect_fx(text: str) -> tuple[float, str, str] | None:
    names = "|".join(_CCY)
    m = re.search(
        rf"(?:(\d+(?:\.\d+)?)\s*)?({names})\s*(?:to|in)\s*({names})",
        text,
        re.I,
    )
    if not m:
        return None
    amount = float(m.group(1) or 1)
    return amount, _CCY[m.group(2).lower()], _CCY[m.group(3).lower()]
