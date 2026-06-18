"""FastAPI application: REST control plane + live WebSocket for the dashboard."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analytics import compute_analytics
from .config import get_settings
from .database import Trade, init_db, session_scope
from .engine import TradingEngine
from .strategy.orb import Bar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

settings = get_settings()
app = FastAPI(title="YN Finance ORB Bot", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
engine = TradingEngine(settings, manager.broadcast)


@app.on_event("startup")
async def _startup():
    init_db()
    log.info("ORB bot API up. env=%s symbol=%s auto_trade=%s",
             settings.tradovate_env, settings.symbol, settings.auto_trade)


# ----------------------------------------------------------------- schemas
class StrategyUpdate(BaseModel):
    or_candles: int | None = None
    departure_pts: float | None = None
    confirm_close: bool | None = None
    stop_pts: float | None = None
    tp_pts: float | None = None
    one_trade: bool | None = None
    use_vwap: bool | None = None
    use_partial: bool | None = None
    partial_pct: int | None = None
    session: str | None = None


class AutoTradeUpdate(BaseModel):
    enabled: bool


class BacktestBar(BaseModel):
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class TradingViewAlert(BaseModel):
    """Alert payload posted by a TradingView webhook (your Pine Script)."""
    side: str                       # "LONG"/"SHORT" (or buy/sell)
    entry: float
    stop: float | None = None
    target: float | None = None
    secret: str | None = None       # optional shared secret check


# ----------------------------------------------------------------- routes
@app.get("/api/health")
async def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/state")
async def get_state():
    return engine.state()


@app.get("/api/config")
async def get_config():
    c = engine.strategy.cfg
    return {
        "symbol": settings.symbol,
        "env": settings.tradovate_env,
        "point_value": settings.point_value,
        "quantity": settings.quantity,
        "strategy": {
            "session": c.session, "or_candles": c.or_candles,
            "departure_pts": c.departure_pts, "confirm_close": c.confirm_close,
            "stop_pts": c.stop_pts, "tp_pts": c.tp_pts, "one_trade": c.one_trade,
            "use_vwap": c.use_vwap, "use_partial": c.use_partial,
            "partial_pct": c.partial_pct, "timezone": c.timezone,
        },
    }


@app.post("/api/strategy")
async def update_strategy(update: StrategyUpdate):
    params = {k: v for k, v in update.model_dump().items() if v is not None}
    engine.update_strategy(params)
    return {"ok": True, "applied": params}


@app.post("/api/bot/start")
async def start_bot():
    return await engine.start()


@app.post("/api/bot/stop")
async def stop_bot():
    return await engine.stop()


@app.post("/api/bot/kill")
async def kill_bot():
    return await engine.kill_switch()


@app.post("/api/bot/auto-trade")
async def set_auto_trade(update: AutoTradeUpdate):
    engine.set_auto_trade(update.enabled)
    await manager.broadcast({"type": "state", "data": engine.state()})
    return {"ok": True, "auto_trade": update.enabled}


@app.get("/api/trades")
async def list_trades(limit: int = 200):
    with session_scope() as s:
        rows = s.query(Trade).order_by(Trade.opened_at.desc()).limit(limit).all()
        return [t.to_dict() for t in rows]


@app.get("/api/analytics")
async def analytics():
    return compute_analytics()


@app.post("/api/backtest")
async def backtest(bars: list[BacktestBar]):
    """Replay historical bars through the strategy (no orders sent)."""
    prev_auto = engine.auto_trade
    engine.set_auto_trade(False)
    parsed = [
        Bar(ts=datetime.fromisoformat(b.ts.replace("Z", "+00:00")), open=b.open,
            high=b.high, low=b.low, close=b.close, volume=b.volume)
        for b in bars
    ]
    result = await engine.replay_bars(parsed)
    engine.set_auto_trade(prev_auto)
    return result


@app.post("/api/webhook/tradingview")
async def tradingview_webhook(alert: TradingViewAlert):
    """Receive a signal from the Pine Script (via TradingView alert webhook),
    log it, and route execution through the configured broker (TradersPost for
    Lucid). This lets the original indicator be the signal source — no live
    market-data feed required on our side.
    """
    side = alert.side.strip().upper()
    side = {"BUY": "LONG", "SELL": "SHORT"}.get(side, side)
    result = await engine.submit_external_signal(
        side=side, entry=alert.entry, stop=alert.stop, target=alert.target,
    )
    await manager.broadcast({"type": "state", "data": engine.state()})
    return result


@app.delete("/api/trades")
async def clear_trades():
    with session_scope() as s:
        s.query(Trade).delete()
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json({"type": "state", "data": engine.state()})
        while True:
            # Keep the socket open; the client doesn't need to send anything.
            await asyncio.wait_for(ws.receive_text(), timeout=3600)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        manager.disconnect(ws)
    except Exception:  # noqa: BLE001
        manager.disconnect(ws)
