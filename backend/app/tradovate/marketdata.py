"""Tradovate market-data WebSocket: streams 5-minute chart bars to a callback.

Implements Tradovate's frame protocol:
  - text frames are prefixed by a type char: 'o' open, 'h' heartbeat,
    'a' JSON-array payload, 'c' close.
  - requests are sent as:  "<endpoint>\\n<request-id>\\n<query>\\n<body>"
  - keep-alive is an empty "[]" frame every ~2.5s.

On connect it authorizes with the md token and subscribes to a 5-minute
MinuteBar chart for the configured symbol. Closed bars are forwarded via the
`on_bar` callback; the most recent (still-forming) bar is held back until the
next bar opens so the strategy only ever sees CLOSED candles.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Awaitable, Callable

import websockets

from ..config import Settings
from ..strategy.orb import Bar

log = logging.getLogger("tradovate.md")

BarCb = Callable[[Bar], Awaitable[None]]
StatusCb = Callable[[str], None]


class MarketDataClient:
    def __init__(self, settings: Settings, md_token: str, on_bar: BarCb, on_status: StatusCb | None = None):
        self.s = settings
        self.token = md_token
        self.on_bar = on_bar
        self.on_status = on_status or (lambda _s: None)
        self._req_id = 0
        self._ws = None
        self._running = False
        self._chart_minutes = 5
        # last closed bar timestamp we forwarded (de-dupe / detect bar close)
        self._open_bar_ts: datetime | None = None
        self._open_bar: Bar | None = None

    async def run(self) -> None:
        self._running = True
        url = self.s.hosts["md"]
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=None, max_size=None) as ws:
                    self._ws = ws
                    self.on_status("connecting")
                    await self._handshake(ws)
                    self.on_status("streaming")
                    backoff = 1
                    hb = asyncio.create_task(self._heartbeat(ws))
                    try:
                        async for raw in ws:
                            await self._on_frame(raw)
                    finally:
                        hb.cancel()
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                self.on_status("disconnected")
                log.warning("MD socket error: %s (reconnect in %ss)", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
        self.on_status("stopped")

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------- protocol
    async def _handshake(self, ws) -> None:
        # First frame should be 'o' (open). Authorize, then subscribe to chart.
        first = await ws.recv()
        if not str(first).startswith("o"):
            log.debug("Unexpected first frame: %s", first)
        await self._send(ws, "authorize", "", self.token)
        await asyncio.sleep(0.2)
        await self._subscribe_chart(ws)

    async def _subscribe_chart(self, ws) -> None:
        body = json.dumps({
            "symbol": self.s.symbol,
            "chartDescription": {
                "underlyingType": "MinuteBar",
                "elementSize": self._chart_minutes,
                "elementSizeUnit": "UnderlyingUnits",
                "withHistogram": False,
            },
            "timeRange": {"asMuchAsElements": 60},
        })
        await self._send(ws, "md/getChart", "", body)
        log.info("Subscribed to %s %dm chart", self.s.symbol, self._chart_minutes)

    async def _send(self, ws, endpoint: str, query: str, body: str) -> None:
        self._req_id += 1
        frame = f"{endpoint}\n{self._req_id}\n{query}\n{body}"
        await ws.send(frame)

    async def _heartbeat(self, ws) -> None:
        try:
            while True:
                await asyncio.sleep(2.5)
                await ws.send("[]")
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            return

    async def _on_frame(self, raw) -> None:
        text = str(raw)
        if not text:
            return
        kind, payload = text[0], text[1:]
        if kind == "h":  # server heartbeat
            return
        if kind == "c":
            self.on_status("disconnected")
            return
        if kind != "a":
            return
        try:
            messages = json.loads(payload) if payload else []
        except json.JSONDecodeError:
            return
        for msg in messages:
            await self._handle_message(msg)

    async def _handle_message(self, msg: dict) -> None:
        if not isinstance(msg, dict):
            return
        # Event payloads: {"e":"chart","d":{"charts":[...]}}
        if msg.get("e") == "chart":
            charts = (msg.get("d") or {}).get("charts", [])
            for chart in charts:
                for raw_bar in chart.get("bars", []):
                    await self._ingest_bar(raw_bar)
        # Response to getChart can also carry historical bars under "d".
        elif "d" in msg and isinstance(msg["d"], dict) and "charts" in msg["d"]:
            for chart in msg["d"]["charts"]:
                for raw_bar in chart.get("bars", []):
                    await self._ingest_bar(raw_bar)

    async def _ingest_bar(self, raw: dict) -> None:
        """Forward a bar only once its successor appears (i.e. it has CLOSED)."""
        ts = self._parse_ts(raw.get("timestamp"))
        if ts is None:
            return
        up = float(raw.get("upVolume", 0) or 0)
        down = float(raw.get("downVolume", 0) or 0)
        bar = Bar(
            ts=ts,
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=up + down,
        )
        if self._open_bar_ts is None:
            self._open_bar_ts = ts
            self._open_bar = bar
            return
        if ts == self._open_bar_ts:
            # update of the still-forming bar
            self._open_bar = bar
            return
        if ts > self._open_bar_ts:
            # a newer bar opened -> the previous one is now closed; emit it.
            if self._open_bar is not None:
                await self.on_bar(self._open_bar)
            self._open_bar_ts = ts
            self._open_bar = bar

    @staticmethod
    def _parse_ts(value) -> datetime | None:
        if value is None:
            return None
        try:
            s = str(value).replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return None
