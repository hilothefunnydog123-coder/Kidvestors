"""TradersPost webhook client.

TradersPost bridges signals to broker/prop accounts (incl. Lucid Trading via
Tradovate/Rithmic) without needing a broker API key on our side. Each strategy
has a unique secret webhook URL; we POST JSON signals to it.

Schema reference: https://docs.traderspost.io/docs/developer-resources/webhook-reference
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

log = logging.getLogger("traderspost")


class TradersPostError(RuntimeError):
    pass


class TradersPostClient:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url)

    @staticmethod
    def build_bracket_payload(
        *, side: str, ticker: str, qty: int, target: float, stop: float,
        signal_price: float | None = None,
    ) -> dict:
        """Map an ORB signal to a TradersPost market-entry bracket payload."""
        return {
            "ticker": ticker,
            "action": "buy" if side == "LONG" else "sell",
            "sentiment": "bullish" if side == "LONG" else "bearish",
            "orderType": "market",
            "quantity": qty,
            "quantityType": "fixed_quantity",
            "price": signal_price,
            "time": datetime.now(timezone.utc).isoformat(),
            "takeProfit": {"limitPrice": round(target, 2)},
            "stopLoss": {"type": "stop", "stopPrice": round(stop, 2)},
        }

    async def send_bracket(self, **kwargs) -> dict:
        return await self._post(self.build_bracket_payload(**kwargs))

    async def exit_position(self, ticker: str) -> dict:
        """Flatten the position (kill-switch / manual exit)."""
        return await self._post({
            "ticker": ticker, "action": "exit",
            "time": datetime.now(timezone.utc).isoformat(),
        })

    async def _post(self, payload: dict) -> dict:
        if not self.configured:
            raise TradersPostError("TradersPost webhook URL not configured (.env).")
        clean = {k: v for k, v in payload.items() if v is not None}
        r = await self._http.post(self.webhook_url, json=clean)
        if r.status_code >= 400:
            raise TradersPostError(f"TradersPost HTTP {r.status_code}: {r.text[:200]}")
        log.info("TradersPost signal sent: %s %s", clean.get("action"), clean.get("ticker"))
        try:
            return r.json()
        except Exception:  # noqa: BLE001
            return {"ok": True, "status": r.status_code}
