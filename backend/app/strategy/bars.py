"""Aggregate incoming trade prints into fixed-width time bars.

Tradovate's `md/getChart` can deliver 5-minute bars directly, but when we only
have a tick/quote stream we roll our own bars here so the strategy always sees
clean, closed candles.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from .orb import Bar


class BarAggregator:
    def __init__(self, minutes: int, on_close: Callable[[Bar], None]):
        self.width = timedelta(minutes=minutes)
        self.on_close = on_close
        self._cur: Bar | None = None
        self._bucket: datetime | None = None

    def _bucket_start(self, ts: datetime) -> datetime:
        ts = ts.astimezone(timezone.utc)
        epoch_min = int(ts.timestamp() // 60)
        w = int(self.width.total_seconds() // 60)
        floored = (epoch_min // w) * w
        return datetime.fromtimestamp(floored * 60, tz=timezone.utc)

    def add_tick(self, ts: datetime, price: float, volume: float = 0.0) -> None:
        bucket = self._bucket_start(ts)
        if self._cur is None:
            self._open_bar(bucket, price)
        elif bucket != self._bucket:
            # New bucket -> close out the previous bar, then open a fresh one.
            self.on_close(self._cur)
            self._open_bar(bucket, price)
        else:
            c = self._cur
            c.high = max(c.high, price)
            c.low = min(c.low, price)
            c.close = price
            c.volume += volume

    def _open_bar(self, bucket: datetime, price: float) -> None:
        self._bucket = bucket
        self._cur = Bar(ts=bucket, open=price, high=price, low=price, close=price, volume=0.0)
