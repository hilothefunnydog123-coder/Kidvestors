"""Tradovate REST client: auth, account lookup, and bracket order placement.

Works against demo or live (incl. prop-firm accounts that clear through
Tradovate). Endpoints follow the public Tradovate API:
https://api.tradovate.com/

Token renewal is handled transparently. Orders are sent as an OSO/bracket so a
position is never left without a protective stop + target.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from ..config import Settings

log = logging.getLogger("tradovate.client")


class TradovateError(RuntimeError):
    pass


@dataclass
class Account:
    id: int
    name: str
    spec: str


class TradovateClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.rest = settings.hosts["rest"]
        self._token: str | None = None
        self._md_token: str | None = None
        self._token_exp: float = 0.0
        self._http = httpx.AsyncClient(timeout=20.0)
        self.account: Account | None = None

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------ auth
    async def authenticate(self) -> None:
        """Obtain an access token (and a market-data token)."""
        if not self.s.credentials_present:
            raise TradovateError("Tradovate credentials are not configured (.env).")

        body = {
            "name": self.s.tradovate_username,
            "password": self.s.tradovate_password,
            "appId": self.s.tradovate_app_id,
            "appVersion": self.s.tradovate_app_version,
            "cid": self.s.tradovate_cid,
            "sec": self.s.tradovate_secret,
            "deviceId": self.s.tradovate_device_id,
        }
        r = await self._http.post(f"{self.rest}/auth/accesstokenrequest", json=body)
        data = self._json(r)
        if "accessToken" not in data:
            raise TradovateError(f"Auth failed: {data.get('errorText') or data}")

        self._token = data["accessToken"]
        self._md_token = data.get("mdAccessToken", self._token)
        # expirationTime is ISO; renew a minute early using a coarse TTL.
        self._token_exp = time.time() + 60 * 70
        log.info("Tradovate authenticated (env=%s)", self.s.tradovate_env)
        await self._resolve_account()

    async def _ensure_token(self) -> None:
        if self._token is None or time.time() >= self._token_exp:
            await self.authenticate()

    @property
    def md_token(self) -> str | None:
        return self._md_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    # --------------------------------------------------------------- accounts
    async def _resolve_account(self) -> None:
        r = await self._http.get(f"{self.rest}/account/list", headers=self._headers())
        accounts = self._json(r)
        if not isinstance(accounts, list) or not accounts:
            raise TradovateError("No Tradovate accounts returned for this login.")

        chosen = None
        if self.s.tradovate_account_id:
            chosen = next((a for a in accounts if a.get("id") == self.s.tradovate_account_id), None)
        if chosen is None and self.s.tradovate_account_spec:
            chosen = next((a for a in accounts if a.get("name") == self.s.tradovate_account_spec), None)
        if chosen is None:
            chosen = accounts[0]

        self.account = Account(id=chosen["id"], name=chosen.get("name", ""), spec=chosen.get("name", ""))
        log.info("Trading account resolved: %s (id=%s)", self.account.name, self.account.id)

    async def get_cash_balance(self) -> dict | None:
        await self._ensure_token()
        if not self.account:
            return None
        r = await self._http.get(
            f"{self.rest}/cashBalance/getcashbalancesnapshot",
            headers=self._headers(),
            params={"accountId": self.account.id},
        )
        try:
            return self._json(r)
        except TradovateError:
            return None

    async def list_positions(self) -> list[dict]:
        await self._ensure_token()
        r = await self._http.get(f"{self.rest}/position/list", headers=self._headers())
        try:
            data = self._json(r)
            if not self.account:
                return data if isinstance(data, list) else []
            return [p for p in data if p.get("accountId") == self.account.id] if isinstance(data, list) else []
        except TradovateError:
            return []

    # ----------------------------------------------------------------- orders
    async def place_bracket(
        self, *, side: str, entry: float, stop: float, target: float, qty: int, symbol: str,
    ) -> dict:
        """Place an OSO bracket: market entry + protective stop + limit target.

        `side` is "LONG" or "SHORT".
        """
        await self._ensure_token()
        if not self.account:
            raise TradovateError("No account resolved; cannot place order.")

        action = "Buy" if side == "LONG" else "Sell"
        exit_action = "Sell" if side == "LONG" else "Buy"

        body = {
            "accountSpec": self.account.spec,
            "accountId": self.account.id,
            "action": action,
            "symbol": symbol,
            "orderQty": qty,
            "orderType": "Market",
            "isAutomated": True,
            "bracket1": {
                "action": exit_action,
                "orderType": "Stop",
                "stopPrice": round(stop, 2),
            },
            "bracket2": {
                "action": exit_action,
                "orderType": "Limit",
                "price": round(target, 2),
            },
        }
        r = await self._http.post(
            f"{self.rest}/order/placeOSO", headers=self._headers(), json=body,
        )
        data = self._json(r)
        if data.get("failureReason"):
            raise TradovateError(f"Order rejected: {data.get('failureText') or data['failureReason']}")
        log.info("Bracket placed: %s %s x%s @mkt stop=%s tp=%s", action, symbol, qty, stop, target)
        return data

    async def flatten(self, symbol: str) -> dict | None:
        """Liquidate any open position in `symbol` (panic / kill-switch)."""
        await self._ensure_token()
        if not self.account:
            return None
        body = {"accountId": self.account.id, "symbol": symbol, "admin": False}
        r = await self._http.post(
            f"{self.rest}/order/liquidateposition", headers=self._headers(), json=body,
        )
        try:
            return self._json(r)
        except TradovateError as e:
            log.warning("Flatten failed: %s", e)
            return None

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _json(r: httpx.Response) -> dict | list:
        if r.status_code == 401:
            raise TradovateError("Unauthorized (token expired or bad credentials).")
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            raise TradovateError(f"Non-JSON response {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400 and isinstance(data, dict):
            raise TradovateError(data.get("errorText") or f"HTTP {r.status_code}: {data}")
        return data
