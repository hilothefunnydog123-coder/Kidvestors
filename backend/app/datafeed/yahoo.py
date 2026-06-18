"""Free market-data feed via Yahoo Finance's chart endpoint.

No API key required. NOTE: Yahoo futures data is typically delayed ~10-15
minutes, so this is great for paper-trading / validation but will give worse
fills than a real-time feed. `NQ=F` trades at the same price as MNQ, so it
drives MNQ signals directly.

Polls every `poll_seconds`, parses 5-minute OHLCV bars, and forwards only
CLOSED bars (the most recent element is the still-forming bar and is held back).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

from ..strategy.orb import Bar

log = logging.getLogger("datafeed.yahoo")

BarCb = Callable[[Bar], Awaitable[None]]
StatusCb = Callable[[str], None]

_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


class YahooFeed:
    def __init__(self, symbol: str, on_bar: BarCb, on_status: StatusCb | None = None,
                 interval: str = "5m", poll_seconds: int = 60):
        self.symbol = symbol
        self.on_bar = on_bar
        self.on_status = on_status or (lambda _s: None)
        self.interval = interval
        self.poll_seconds = poll_seconds
        self._running = False
        self._last_emitted_ts: int = 0
        self._http = httpx.AsyncClient(timeout=15.0, headers=_HEADERS)

    @staticmethod
    def parse(payload: dict) -> list[Bar]:
        """Convert a Yahoo chart JSON response into a list of Bar objects."""
        result = (payload.get("chart") or {}).get("result")
        if not result:
            return []
        r = result[0]
        ts = r.get("timestamp") or []
        quote = ((r.get("indicators") or {}).get("quote") or [{}])[0]
        opens, highs = quote.get("open", []), quote.get("high", [])
        lows, closes = quote.get("low", []), quote.get("close", [])
        vols = quote.get("volume", [])
        bars: list[Bar] = []
        for i, t in enumerate(ts):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            if None in (o, h, l, c):
                continue  # gaps in the series
            bars.append(Bar(
                ts=datetime.fromtimestamp(t, tz=timezone.utc),
                open=float(o), high=float(h), low=float(l), close=float(c),
                volume=float(vols[i]) if i < len(vols) and vols[i] is not None else 0.0,
            ))
        return bars

    async def _fetch(self) -> list[Bar]:
        params = {"interval": self.interval, "range": "5d", "includePrePost": "true"}
        r = await self._http.get(_URL.format(symbol=self.symbol), params=params)
        r.raise_for_status()
        return self.parse(r.json())

    async def run(self) -> None:
        self._running = True
        backoff = 2
        while self._running:
            try:
                bars = await self._fetch()
                self.on_status("streaming")
                backoff = 2
                # The last bar is still forming; only emit fully-closed bars.
                for bar in bars[:-1]:
                    epoch = int(bar.ts.timestamp())
                    if epoch > self._last_emitted_ts:
                        self._last_emitted_ts = epoch
                        await self.on_bar(bar)
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                self.on_status("disconnected")
                log.warning("Yahoo feed error: %s (retry in %ss)", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            await asyncio.sleep(self.poll_seconds)
        self.on_status("stopped")
        await self._http.aclose()

    def stop(self) -> None:
        self._running = False
