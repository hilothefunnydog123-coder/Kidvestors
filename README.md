# YN Finance — ORB Retest Auto-Trading Bot

An AI/algorithmic auto-trading bot that runs the **6:30 Opening-Range-Breakout
Retest** strategy (a faithful Python port of the original Pine Script) against a
**Tradovate** account — including prop-firm accounts (Apex, Topstep, Tradeify,
etc.) that clear through Tradovate.

It does three things:

1. **Streams live 5-minute bars** from Tradovate's market-data WebSocket.
2. **Runs the ORB-retest strategy** server-side and **auto-places bracket
   orders** (entry + stop + target, with a scale-out to breakeven at +1R).
3. **Serves a live dashboard** with connection status, the current opening
   range, open position, a trade log, an equity curve, and full analytics
   (win rate, expectancy, R-multiples, profit factor, etc.).

> ⚠️ **This trades real money once connected to a funded account.** Start in
> Tradovate **demo** mode (`TRADOVATE_ENV=demo`) and only flip to `live` after
> you've watched it behave for a full session. Algorithmic trading can lose
> money fast. You are responsible for every order it sends.

---

## Architecture

```
Tradovate Market Data (WS)  ──►  Bar builder ──►  ORB Strategy ──►  Signals
                                                                       │
                                                                       ▼
                                              Tradovate Orders API (bracket OCO)
                                                                       │
        SQLite (trades, signals, equity)  ◄────────────────────────────┘
                                                                       │
        FastAPI REST + WebSocket  ──►  React dashboard (live updates)  ◄┘
```

- `backend/` — Python (FastAPI) service: Tradovate client, strategy engine,
  database, analytics, REST + WebSocket API.
- `frontend/` — React + Vite dashboard.

---

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env with your credentials
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                       # opens http://localhost:5173
```

The dashboard talks to the backend at `http://localhost:8000` (override with
`VITE_API_BASE`).

---

## Configuration (`.env`)

| Variable | Meaning |
| --- | --- |
| `TRADOVATE_ENV` | `demo` or `live`. **Keep `demo` until verified.** |
| `TRADOVATE_USERNAME` / `TRADOVATE_PASSWORD` | Your Tradovate / prop-firm login. |
| `TRADOVATE_APP_ID` / `TRADOVATE_APP_VERSION` | From your Tradovate API app registration. |
| `TRADOVATE_CID` / `TRADOVATE_SECRET` | API key credentials (`cid` + `sec`). |
| `TRADOVATE_DEVICE_ID` | Stable per-device UUID (any fixed string). |
| `TRADOVATE_ACCOUNT_SPEC` / `TRADOVATE_ACCOUNT_ID` | The account to trade (your prop account). |
| `SYMBOL` | Contract to trade, e.g. `MNQM5`, `ESU5`. |
| `AUTO_TRADE` | `true` to actually send orders, `false` for signals-only (paper log). |

Strategy parameters (opening-range size, stop/target points, VWAP filter, etc.)
mirror the Pine Script inputs and are editable live from the dashboard or via
`STRATEGY_*` env vars — see `.env.example`.

---

## How the strategy maps to the Pine Script

The Python port in `backend/app/strategy/orb.py` reproduces the original
indicator bar-for-bar:

- Builds the opening range from the first N candles of the `06:30–13:00 PT`
  session.
- Tracks independent long/short **breaks** (a *close* beyond the range) and
  **departures** (price running `departurePts` past the level).
- A signal fires on the **retest**: prior-bar departure confirmed, price
  returns to the level, optional close-back-beyond confirmation, optional VWAP
  filter.
- Manages the trade exactly like the script: stop, target, and a scale-out at
  **+1R** that moves the remaining stop to breakeven.

See `backend/app/strategy/orb.py` for the line-by-line mapping.

---

## Safety notes

- Defaults to **one trade per day** and **signals-only** (`AUTO_TRADE=false`).
- Every order is a **bracket** (OCO stop + target) so a crash never leaves a
  naked position unprotected.
- Nothing about your credentials is committed — `.env` is git-ignored.
- This is software for **your own** account. It is not financial advice.
