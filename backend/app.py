"""MOROS AGI HTTP interface."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.agent import moros
from backend.memory import store
from backend.public_apis import CATALOG, SOURCE, dashboard_feeds, github_catalog
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


@app.post("/api/chat")
async def chat(body: ChatIn):
    return await moros.think(body.message, body.session_id)


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")
