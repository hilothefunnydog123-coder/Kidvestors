"""Trading engine: wires market data -> strategy -> execution -> persistence.

Replicates the Pine Script trade management:
  - enter on a retest signal (bracket: stop + target),
  - at +1R scale out `partial_pct`% and move the remaining stop to breakeven,
  - exit at target, breakeven, or stop.

PnL and outcomes are tracked from the bar stream so analytics are always
populated even in signals-only mode. When AUTO_TRADE is on, a real OSO bracket
is sent to Tradovate so the position is broker-protected regardless of process
state.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .analytics import compute_analytics
from .config import Settings
from .database import Trade, session_scope
from .strategy.orb import Bar, ORBStrategy, Signal, StrategyConfig
from .tradovate.client import TradovateClient, TradovateError
from .tradovate.marketdata import MarketDataClient
from .traderspost import TradersPostClient, TradersPostError
from .datafeed.yahoo import YahooFeed

log = logging.getLogger("engine")

Broadcast = Callable[[dict], Awaitable[None]]


class OpenPosition:
    def __init__(self, trade_id: int, signal: Signal, qty: int):
        self.trade_id = trade_id
        self.side = signal.side
        self.entry = signal.entry
        self.stop = signal.stop
        self.target = signal.target
        self.r1 = signal.r1
        self.qty = qty
        self.be_moved = False
        self.scaled = False


class TradingEngine:
    def __init__(self, settings: Settings, broadcast: Broadcast):
        self.s = settings
        self.broadcast = broadcast
        self.strategy = ORBStrategy(settings.symbol, self._strategy_config())
        self.client = TradovateClient(settings)
        self.traderspost = TradersPostClient(settings.traderspost_webhook_url)
        self.md: MarketDataClient | None = None
        self.yahoo: YahooFeed | None = None
        self._md_task: asyncio.Task | None = None
        self.position: OpenPosition | None = None

        self.running = False
        self.auto_trade = settings.auto_trade
        self.connection = "disconnected"
        self.last_bar: Bar | None = None
        self.account_info: dict | None = None
        self.last_error: str | None = None

    # ----------------------------------------------------------- lifecycle
    def _strategy_config(self) -> StrategyConfig:
        p = self.s.strategy
        return StrategyConfig(
            timezone=p.timezone, session=p.session, or_candles=p.or_candles,
            departure_pts=p.departure_pts, confirm_close=p.confirm_close,
            stop_pts=p.stop_pts, tp_pts=p.tp_pts, one_trade=p.one_trade,
            use_vwap=p.use_vwap, use_partial=p.use_partial, partial_pct=p.partial_pct,
        )

    async def start(self) -> dict:
        if self.running:
            return self.state()
        self.last_error = None

        # Authenticate Tradovate only if it's needed for execution or data.
        if self.s.broker == "tradovate" or self.s.data_feed == "tradovate":
            try:
                await self.client.authenticate()
                self.account_info = await self.client.get_cash_balance()
            except TradovateError as e:
                self.last_error = str(e)
                log.warning("Tradovate auth failed: %s", e)
                await self._emit()
                return self.state()

        # Start the market-data feed that drives the strategy engine.
        if self.s.data_feed == "yahoo":
            self.yahoo = YahooFeed(self.s.feed_symbol, self._on_bar, self._on_status)
            self._md_task = asyncio.create_task(self.yahoo.run())
            self.connection = "connecting"
            log.info("Yahoo feed started for %s -> signals route to %s",
                     self.s.feed_symbol, self.s.broker)
        elif self.s.data_feed == "tradovate":
            token = self.client.md_token or ""
            self.md = MarketDataClient(self.s, token, self._on_bar, self._on_status)
            self._md_task = asyncio.create_task(self.md.run())
        else:
            # No internal feed: signals arrive via the TradingView webhook.
            self.connection = "webhook-ready"
            if self.s.broker == "traderspost" and not self.traderspost.configured:
                self.last_error = "TradersPost webhook URL not set (.env)."

        self.running = True
        await self._emit()
        return self.state()

    async def stop(self) -> dict:
        self.running = False
        if self.md:
            self.md.stop()
        if self.yahoo:
            self.yahoo.stop()
        if self._md_task:
            self._md_task.cancel()
        self.connection = "stopped"
        await self._emit()
        return self.state()

    async def kill_switch(self) -> dict:
        """Flatten any open position immediately and stop trading."""
        try:
            if self.s.broker == "traderspost":
                if self.traderspost.configured:
                    await self.traderspost.exit_position(self.s.exec_ticker)
            else:
                await self.client.flatten(self.s.symbol)
        except (TradovateError, TradersPostError) as e:
            self.last_error = str(e)
        if self.position:
            await self._close_trade(self.position, self.position.entry, "FLATTENED",
                                    datetime.now(timezone.utc))
        await self.stop()
        return self.state()

    def set_auto_trade(self, enabled: bool) -> None:
        self.auto_trade = enabled

    def update_strategy(self, params: dict) -> None:
        cfg = self.strategy.cfg
        for k, v in params.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        log.info("Strategy params updated: %s", params)

    def _on_status(self, status: str) -> None:
        self.connection = status
        asyncio.create_task(self._emit())

    # --------------------------------------------------------------- bars
    async def _on_bar(self, bar: Bar) -> None:
        self.last_bar = bar
        signal = self.strategy.on_bar(bar)

        if signal and self.position is None:
            await self._open_trade(signal, bar)

        if self.position is not None:
            await self._manage(bar)

        await self._emit(bar=bar)

    async def _open_trade(self, signal: Signal, bar: Bar | None) -> None:
        qty = self.s.quantity
        live = False
        if self.auto_trade:
            try:
                if self.s.broker == "traderspost":
                    await self.traderspost.send_bracket(
                        side=signal.side, ticker=self.s.exec_ticker, qty=qty,
                        target=signal.target, stop=signal.stop,
                        signal_price=signal.entry,
                    )
                else:
                    await self.client.place_bracket(
                        side=signal.side, entry=signal.entry, stop=signal.stop,
                        target=signal.target, qty=qty, symbol=self.s.symbol,
                    )
                live = True
            except (TradovateError, TradersPostError) as e:
                self.last_error = f"Order failed: {e}"
                log.error(self.last_error)

        with session_scope() as s:
            t = Trade(
                symbol=self.s.symbol, side=signal.side, entry=signal.entry,
                stop=signal.stop, target=signal.target, r1=signal.r1, qty=qty,
                opened_at=signal.bar_ts, outcome="OPEN", live=live,
                note=signal.reason,
            )
            s.add(t)
            s.flush()
            trade_id = t.id

        self.position = OpenPosition(trade_id, signal, qty)
        log.info("OPEN %s %s @ %.2f (stop %.2f / tp %.2f) live=%s",
                 signal.side, self.s.symbol, signal.entry, signal.stop, signal.target, live)
        await self.broadcast({"type": "signal", "data": {
            "side": signal.side, "entry": signal.entry, "stop": signal.stop,
            "target": signal.target, "ts": signal.bar_ts.isoformat(), "live": live,
        }})

    async def submit_external_signal(
        self, *, side: str, entry: float, stop: float | None = None,
        target: float | None = None,
    ) -> dict:
        """Open a trade from an external signal (e.g. a TradingView alert).

        Lets the bot use the original Pine Script as the signal source while we
        handle execution (TradersPost/Tradovate), logging, and analytics.
        """
        side = side.upper()
        if side not in ("LONG", "SHORT"):
            return {"ok": False, "error": f"invalid side {side!r}"}
        if self.position is not None:
            return {"ok": False, "error": "position already open"}

        cfg = self.strategy.cfg
        if stop is None:
            stop = entry - cfg.stop_pts if side == "LONG" else entry + cfg.stop_pts
        if target is None:
            target = entry + cfg.tp_pts if side == "LONG" else entry - cfg.tp_pts
        risk = abs(entry - stop)
        r1 = entry + risk if side == "LONG" else entry - risk

        signal = Signal(
            side=side, entry=entry, stop=stop, target=target, r1=r1,
            bar_ts=datetime.now(timezone.utc), symbol=self.s.symbol,
            reason="TradingView webhook",
        )
        await self._open_trade(signal, None)
        await self._emit()
        return {"ok": True, "trade_id": self.position.trade_id if self.position else None}

    async def _manage(self, bar: Bar) -> None:
        pos = self.position
        if pos is None:
            return
        long = pos.side == "LONG"
        cfg = self.strategy.cfg

        # +1R -> scale out and move stop to breakeven
        if cfg.use_partial and not pos.be_moved:
            hit_r1 = bar.high >= pos.r1 if long else bar.low <= pos.r1
            if hit_r1:
                pos.be_moved = True
                pos.scaled = True
                with session_scope() as s:
                    t = s.get(Trade, pos.trade_id)
                    if t:
                        t.be_moved = True
                        t.scaled = True
                log.info("+1R reached -> scale %d%% and stop to BE", cfg.partial_pct)
                await self.broadcast({"type": "scale", "data": {"trade_id": pos.trade_id}})

        cur_stop = pos.entry if pos.be_moved else pos.stop
        now = bar.ts

        # Target first, then stop (mirrors the Pine ordering).
        if (bar.high >= pos.target) if long else (bar.low <= pos.target):
            await self._close_trade(pos, pos.target, "TARGET", now)
        elif (bar.low <= cur_stop) if long else (bar.high >= cur_stop):
            outcome = "BREAKEVEN" if pos.be_moved else "STOP"
            await self._close_trade(pos, cur_stop, outcome, now)

    async def _close_trade(self, pos: OpenPosition, exit_price: float, outcome: str,
                           when: datetime) -> None:
        pnl, r = self._pnl(pos, exit_price)
        with session_scope() as s:
            t = s.get(Trade, pos.trade_id)
            if t:
                t.closed_at = when
                t.exit_price = exit_price
                t.outcome = outcome
                t.pnl = round(pnl, 2)
                t.r_multiple = round(r, 3)
        log.info("CLOSE %s %s @ %.2f -> %s  pnl=$%.2f (%.2fR)",
                 pos.side, self.s.symbol, exit_price, outcome, pnl, r)
        self.position = None
        await self.broadcast({"type": "trade_closed", "data": {
            "trade_id": pos.trade_id, "outcome": outcome, "pnl": round(pnl, 2),
        }})

    def _pnl(self, pos: OpenPosition, exit_price: float) -> tuple[float, float]:
        """$ PnL and R-multiple, accounting for a +1R partial scale-out."""
        cfg = self.strategy.cfg
        pv = self.s.point_value
        sign = 1.0 if pos.side == "LONG" else -1.0
        risk_pts = cfg.stop_pts

        scaled_frac = (cfg.partial_pct / 100.0) if pos.scaled else 0.0
        rem_frac = 1.0 - scaled_frac

        # Scaled portion locked in at +1R (= +stop_pts in favorable direction).
        scaled_pts = risk_pts * scaled_frac
        rem_pts = sign * (exit_price - pos.entry) * rem_frac
        total_pts = scaled_pts + rem_pts

        pnl = total_pts * pv * pos.qty
        risk_dollars = risk_pts * pv * pos.qty
        r = pnl / risk_dollars if risk_dollars else 0.0
        return pnl, r

    # --------------------------------------------------------------- state
    def state(self) -> dict:
        pos = None
        if self.position:
            pos = {
                "trade_id": self.position.trade_id, "side": self.position.side,
                "entry": self.position.entry, "stop": self.position.stop,
                "target": self.position.target, "r1": self.position.r1,
                "qty": self.position.qty, "be_moved": self.position.be_moved,
                "scaled": self.position.scaled,
            }
        return {
            "running": self.running,
            "auto_trade": self.auto_trade,
            "connection": self.connection,
            "env": self.s.tradovate_env,
            "symbol": self.s.symbol,
            "broker": self.s.broker,
            "execution_ready": self.s.execution_ready,
            "credentials_present": self.s.credentials_present,
            "account": {
                "name": self.client.account.name if self.client.account else None,
                "id": self.client.account.id if self.client.account else None,
            },
            "cash": self.account_info,
            "strategy_state": self.strategy.snapshot(),
            "position": pos,
            "last_bar": {
                "ts": self.last_bar.ts.isoformat(), "open": self.last_bar.open,
                "high": self.last_bar.high, "low": self.last_bar.low,
                "close": self.last_bar.close,
            } if self.last_bar else None,
            "last_error": self.last_error,
        }

    async def _emit(self, bar: Bar | None = None) -> None:
        payload = {"type": "state", "data": self.state()}
        if bar is not None:
            payload["bar"] = {
                "ts": bar.ts.isoformat(), "open": bar.open, "high": bar.high,
                "low": bar.low, "close": bar.close,
            }
        await self.broadcast(payload)

    async def replay_bars(self, bars: list[Bar]) -> dict:
        """Feed historical bars through a FRESH strategy (backtest / demo).

        Uses an isolated strategy + position so a replay is deterministic and
        never inherits or mutates live in-session state.
        """
        saved_strategy, saved_position = self.strategy, self.position
        self.strategy = ORBStrategy(self.s.symbol, self._strategy_config())
        self.position = None
        try:
            for b in bars:
                await self._on_bar(b)
            # Force-close any still-open backtest trade at the last bar's close
            # so analytics aren't skewed by a dangling OPEN position.
            if self.position is not None and bars:
                await self._close_trade(self.position, bars[-1].close, "FLATTENED", bars[-1].ts)
        finally:
            self.strategy, self.position = saved_strategy, saved_position
        return compute_analytics()
