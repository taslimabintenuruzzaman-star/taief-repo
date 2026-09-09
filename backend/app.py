"""MOROS AGI HTTP interface."""

from __future__ import annotations

from pathlib import Path

from urllib.parse import urlparse

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.agent import moros
from backend.memory import store
from backend.public_apis import CATALOG, SOURCE, dashboard_feeds, github_catalog
from backend.stt import brain_status, transcribe
from moros_agi_core.config.settings import get_settings
from backend.tools import system_status, time_report, weather_dhaka

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(
    title="MOROS AGI",
    description="Modular Operational Reasoning & Oversight System",
    version="1.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def voice_headers(request, call_next):
    response = await call_next(request)
    response.headers["Permissions-Policy"] = "microphone=*, autoplay=*"
    response.headers["Feature-Policy"] = "microphone *; autoplay *"
    return response


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = "default"


@app.get("/api/health")
async def health():
    return {"status": "online", "system": "MOROS AGI", "version": "1.1.0", "apis": SOURCE}


@app.get("/api/status")
async def status():
    return {"time": time_report(), "system": system_status()}


@app.get("/api/memory")
async def memory():
    return {"facts": store.recall(), "notes": store.notes()}


@app.get("/api/catalog")
async def catalog():
    try:
        return await github_catalog()
    except Exception:
        return {"source": SOURCE, "wired": CATALOG, "live": False}


@app.get("/api/feeds")
async def feeds():
    payload = await dashboard_feeds()
    try:
        payload["weather"] = await weather_dhaka()
    except Exception as exc:
        payload["weather"] = {"error": str(exc)}
    return payload


@app.get("/api/brain")
async def brain():
    return brain_status()


@app.get("/api/gemini-runtime")
async def gemini_runtime(request: Request):
    """Browser Gemini path when this host cannot TLS to Google."""
    host = request.headers.get("host", "")
    origin = request.headers.get("origin", "")
    if origin:
        oh = urlparse(origin).netloc
        if oh and host and oh != host:
            return {"ok": False, "key": ""}
    settings = get_settings()
    key = settings.secret(settings.gemini_api_key)
    return {
        "ok": bool(key),
        "key": key,
        "model": settings.gemini_model,
        "model_pro": settings.gemini_model_pro,
    }


@app.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    blob = await file.read()
    if not blob:
        return {"text": "", "error": "empty audio"}
    try:
        return await transcribe(blob, file.filename or "speech.webm")
    except Exception as exc:
        return {"text": "", "error": str(exc)[:240]}


@app.post("/api/chat")
async def chat(body: ChatIn):
    return await moros.think(body.message, body.session_id)


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/voice")
async def voice_booth():
    return FileResponse(FRONTEND / "voice.html")


app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")
