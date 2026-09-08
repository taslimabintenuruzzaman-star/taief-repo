# MOROS AGI

**Modular Operational Reasoning & Oversight System** — a JARVIS-style command deck with a **digital shotta** persona (cursed-king HUD: *Know your place, fool.*).

Live tool bus is wired from the community catalogue **[public-apis/public-apis](https://github.com/public-apis/public-apis)** (no API keys).

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Talk to it

| You say / type | Feed |
| --- | --- |
| *weather* | Open-Meteo (Dhaka) |
| *bitcoin* / *ethereum* | CoinGecko |
| *usd to bdt* / *10 usd to inr* | ExchangeRate-API |
| *news* | Spaceflight News |
| *nasa* | NASA APOD (`DEMO_KEY`) |
| *define gravity* | Free Dictionary |
| *country Bangladesh* | REST Countries |
| *tell me about JARVIS* | Wikipedia |
| *prayer* / *namaz* | Aladhan (Dhaka) |
| *quote* / *joke* / *advice* | ZenQuotes, JokeAPI, Advice Slip |
| *cat fact* / *dog* | Cat Facts, Dog CEO |
| *trivia* | Numbers API |
| *what time is it* / *status* | local clock + diagnostics |
| *remember that my name is Taief* | durable memory |
| *public apis* | list of wired uplinks |

## Hybrid core (`moros_agi_core/`)

Hardware auto-profile (CUDA 11.5GB/4096 ctx vs Vulkan 7.5GB/2048 ctx), dual Ollama routing (`llama3.1:8b` persona, `qwen2.5:7b` code), then failover:

Ollama → Hugging Face → Gemini → Hive → OpenRouter (`google/gemma-4-31b-it:free`).

```bash
cp .env.example .env   # put keys here only — never commit them
python tests/test_moros_live.py
python -m moros_agi_core.main --prompt "status check"
```

Avatar telemetry: `ws://127.0.0.1:8765`. XTTS micro-pause is `0.45s`.

## Stack

- HUD — `frontend/`
- Cognition — `backend/agent.py` (+ optional LLM bridge)
- Router — `moros_agi_core/src/smart_router.py`
- Public APIs — `backend/public_apis.py`
- Memory — `data/memory.json`
