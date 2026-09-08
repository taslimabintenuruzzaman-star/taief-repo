# MOROS AGI

**Modular Operational Reasoning & Oversight System** — a JARVIS-style command deck.

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

## Stack

- HUD — `frontend/`
- Cognition — `backend/agent.py`
- Public APIs — `backend/public_apis.py`
- Memory — `data/memory.json`
