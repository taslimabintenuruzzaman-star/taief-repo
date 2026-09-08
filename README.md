# MOROS AGI

**Modular Operational Reasoning & Oversight System** — a JARVIS-style command deck.

Local full-stack assistant with a holographic HUD, voice I/O, durable memory, and a perceive → recall → plan → act → respond loop.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## What it does

| You say / type | MOROS |
| --- | --- |
| *hello, who are you* | Identity + handshake |
| *what time is it* | Dhaka local clock |
| *weather* | Live Open-Meteo feed for Dhaka |
| *status / diagnostics* | CPU, RAM, disk, host |
| *remember that my name is Taief* | Long-term fact |
| *what do you remember* | Facts + notes |
| *42 * 7* | Safe arithmetic |
| Click the core / MIC | Browser speech recognition + British TTS |

Oversight refuses harmful / criminal requests. No remote system control, no exploit tooling.

## Stack

- **Interface** — Iron Man–inspired HUD (`frontend/`)
- **Cognition** — FastAPI agent (`backend/agent.py`)
- **Memory** — session history + `data/memory.json`
- **Tools** — clock, weather, psutil diagnostics, calculator
