"""
ORB Retest strategy — a faithful Python port of the Pine Script:

    "YN Finance — 6:30 ORB Retest (5m Signals)"

It is fed one CLOSED 5-minute bar at a time via `on_bar()` and emits at most one
signal per call. State is kept exactly like the Pine `var` variables, including
the one-bar lag (`lValid[1]` / `sValid[1]`) that the original uses to require the
departure to be confirmed on a PRIOR bar before a retest counts.

Line-by-line mapping to the indicator is noted in comments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass
class Bar:
    """A single closed bar. `ts` is timezone-aware (UTC)."""
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Signal:
    """A trade signal with its bracket levels, mirroring the Pine entry block."""
    side: str            # "LONG" or "SHORT"
    entry: float         # ePx
    stop: float          # slPx
    target: float        # tpPx
    r1: float            # tp1Px (+1R level for scale-out -> breakeven)
    bar_ts: datetime
    symbol: str
    reason: str = "ORB retest"


@dataclass
class StrategyConfig:
    """Runtime copy of the Pine inputs."""
    timezone: str = "America/Los_Angeles"
    session: str = "0630-1300"
    or_candles: int = 3
    departure_pts: float = 15.0
    confirm_close: bool = True
    stop_pts: float = 50.0
    tp_pts: float = 100.0
    one_trade: bool = True
    use_vwap: bool = True
    use_partial: bool = True
    partial_pct: int = 50

    def session_bounds(self) -> tuple[time, time]:
        start_s, end_s = self.session.split("-")
        start = time(int(start_s[:2]), int(start_s[2:]))
        end = time(int(end_s[:2]), int(end_s[2:]))
        return start, end


class ORBStrategy:
    """Stateful ORB-retest engine. One instance per running symbol."""

    def __init__(self, symbol: str, config: StrategyConfig):
        self.symbol = symbol
        self.cfg = config
        self.tz = ZoneInfo(config.timezone)

        # ----- session / opening-range state (Pine `var`) -----
        self.or_hi: float | None = None
        self.or_lo: float | None = None
        self.cnt = 0
        self.or_done = False
        self.l_broke = False
        self.l_valid = False
        self.s_broke = False
        self.s_valid = False
        self.traded = False

        # one-bar lag for lValid[1] / sValid[1]
        self._l_valid_prev = False
        self._s_valid_prev = False

        # ----- VWAP (daily-resetting session VWAP of hlc3) -----
        self._vwap_pv = 0.0   # sum(hlc3 * volume)
        self._vwap_v = 0.0    # sum(volume)
        self.vwap: float | None = None

        self._session_key: str | None = None  # date string to detect new session

    # ------------------------------------------------------------------ utils
    def _in_session(self, ts_local: datetime) -> bool:
        start, end = self.cfg.session_bounds()
        t = ts_local.time()
        return start <= t < end

    def _hlc3(self, bar: Bar) -> float:
        return (bar.high + bar.low + bar.close) / 3.0

    def snapshot(self) -> dict:
        """Current internal state for the dashboard."""
        return {
            "symbol": self.symbol,
            "or_high": self.or_hi,
            "or_low": self.or_lo,
            "or_done": self.or_done,
            "long_valid": self.l_valid,
            "short_valid": self.s_valid,
            "traded_today": self.traded,
            "vwap": round(self.vwap, 4) if self.vwap is not None else None,
        }

    # ------------------------------------------------------------------ engine
    def on_bar(self, bar: Bar) -> Signal | None:
        """Process one closed 5m bar. Returns a Signal if an entry fires."""
        ts_local = bar.ts.astimezone(self.tz)
        in_sess = self._in_session(ts_local)
        session_key = ts_local.strftime("%Y-%m-%d")

        # newSess: first in-session bar of a new day.
        new_sess = in_sess and session_key != self._session_key
        if new_sess:
            self._reset_session()
            self._session_key = session_key

        # Capture prior-bar validity BEFORE we mutate it this bar (the [1] lag).
        l_valid_prev = self._l_valid_prev
        s_valid_prev = self._s_valid_prev

        if not in_sess:
            # Out of session: VWAP/state untouched, no signals.
            self._l_valid_prev = self.l_valid
            self._s_valid_prev = self.s_valid
            return None

        # ----- VWAP accumulation (session VWAP of hlc3) -----
        self._vwap_pv += self._hlc3(bar) * bar.volume
        self._vwap_v += bar.volume
        if self._vwap_v > 0:
            self.vwap = self._vwap_pv / self._vwap_v

        # ----- build opening range from first or_candles candles -----
        self.cnt += 1
        if self.cnt <= self.cfg.or_candles:
            self.or_hi = bar.high if self.or_hi is None else max(self.or_hi, bar.high)
            self.or_lo = bar.low if self.or_lo is None else min(self.or_lo, bar.low)
            if self.cnt == self.cfg.or_candles:
                self.or_done = True

        signal: Signal | None = None

        # ----- breaks & departures (only once OR is done) -----
        if self.or_done and self.or_hi is not None and self.or_lo is not None:
            if bar.close > self.or_hi:
                self.l_broke = True
            if bar.close < self.or_lo:
                self.s_broke = True
            if self.l_broke and bar.high >= self.or_hi + self.cfg.departure_pts:
                self.l_valid = True
            if self.s_broke and bar.low <= self.or_lo - self.cfg.departure_pts:
                self.s_valid = True

            can_trade = not self.traded or not self.cfg.one_trade

            vwap_ok_long = (not self.cfg.use_vwap) or (self.vwap is not None and bar.close > self.vwap)
            vwap_ok_short = (not self.cfg.use_vwap) or (self.vwap is not None and bar.close < self.vwap)

            # goLong: prior-bar departure (lValid[1]), price returns to level,
            # optional close-back-beyond confirmation, optional VWAP filter.
            go_long = (
                can_trade and l_valid_prev
                and bar.low <= self.or_hi
                and (not self.cfg.confirm_close or bar.close > self.or_hi)
                and vwap_ok_long
            )
            go_short = (
                can_trade and s_valid_prev
                and bar.high >= self.or_lo
                and (not self.cfg.confirm_close or bar.close < self.or_lo)
                and vwap_ok_short
            )

            if go_long:
                signal = self._build_signal("LONG", bar)
                self.traded = True
            elif go_short:
                signal = self._build_signal("SHORT", bar)
                self.traded = True

        # advance the [1] lag
        self._l_valid_prev = self.l_valid
        self._s_valid_prev = self.s_valid
        return signal

    def _build_signal(self, side: str, bar: Bar) -> Signal:
        cfg = self.cfg
        if side == "LONG":
            entry = bar.close if cfg.confirm_close else self.or_hi  # type: ignore[assignment]
            stop = entry - cfg.stop_pts
            target = entry + cfg.tp_pts
            r1 = entry + cfg.stop_pts
        else:
            entry = bar.close if cfg.confirm_close else self.or_lo  # type: ignore[assignment]
            stop = entry + cfg.stop_pts
            target = entry - cfg.tp_pts
            r1 = entry - cfg.stop_pts
        return Signal(
            side=side, entry=float(entry), stop=float(stop), target=float(target),
            r1=float(r1), bar_ts=bar.ts, symbol=self.symbol,
        )

    def _reset_session(self) -> None:
        self.or_hi = None
        self.or_lo = None
        self.cnt = 0
        self.or_done = False
        self.l_broke = False
        self.l_valid = False
        self.s_broke = False
        self.s_valid = False
        self.traded = False
        self._l_valid_prev = False
        self._s_valid_prev = False
        self._vwap_pv = 0.0
        self._vwap_v = 0.0
        self.vwap = None
