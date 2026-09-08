"""Perception-adjacent tools MOROS can invoke while planning."""

from __future__ import annotations

import ast
import operator
import platform
import socket
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import psutil

DHAKA_TZ = ZoneInfo("Asia/Dhaka")
DHAKA = {"lat": 23.8103, "lon": 90.4125, "name": "Dhaka"}

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}

_WMO = {
    0: "clear skies",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}


def local_now() -> datetime:
    return datetime.now(DHAKA_TZ)


def time_report() -> dict:
    now = local_now()
    return {
        "iso": now.isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%A, %d %B %Y"),
        "timezone": "Asia/Dhaka (UTC+6)",
        "spoken": now.strftime("It is %H:%M on %A, %d %B %Y, Asia/Dhaka."),
    }


def system_status() -> dict:
    cpu = psutil.cpu_percent(interval=0.15)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot = datetime.fromtimestamp(psutil.boot_time(), tz=DHAKA_TZ)
    try:
        host = socket.gethostname()
    except OSError:
        host = "moros-node"
    return {
        "host": host,
        "platform": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "disk_percent": disk.percent,
        "uptime_since": boot.strftime("%Y-%m-%d %H:%M"),
        "nominal": cpu < 90 and mem.percent < 92,
    }


def safe_calculate(expr: str) -> str:
    cleaned = (
        expr.lower()
        .replace("calculate", "")
        .replace("what is", "")
        .replace("what's", "")
        .replace("compute", "")
        .replace("equals", "")
        .replace("x", "*")
        .replace("×", "*")
        .replace("÷", "/")
        .strip(" =?")
    )
    tree = ast.parse(cleaned, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.operand))
        raise ValueError("unsupported expression")

    result = _eval(tree)
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"{cleaned} = {result}"


async def weather_dhaka() -> dict:
    params = {
        "latitude": DHAKA["lat"],
        "longitude": DHAKA["lon"],
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,apparent_temperature",
        "timezone": "Asia/Dhaka",
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        res = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        res.raise_for_status()
        current = res.json().get("current", {})
    code = int(current.get("weather_code") or 0)
    desc = _WMO.get(code, "variable conditions")
    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    hum = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")
    spoken = (
        f"In Dhaka it is currently {desc}, {temp} degrees Celsius, "
        f"feeling like {feels}. Humidity {hum} percent, wind {wind} kilometres per hour."
    )
    return {
        "location": "Dhaka, Bangladesh",
        "description": desc,
        "temperature_c": temp,
        "feels_like_c": feels,
        "humidity": hum,
        "wind_kmh": wind,
        "spoken": spoken,
    }
