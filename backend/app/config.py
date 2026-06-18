"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Tradovate API hostnames per environment.
TRADOVATE_HOSTS = {
    "demo": {
        "rest": "https://demo.tradovateapi.com/v1",
        "md": "wss://md-demo.tradovateapi.com/v1/websocket",
        "ws": "wss://demo.tradovateapi.com/v1/websocket",
    },
    "live": {
        "rest": "https://live.tradovateapi.com/v1",
        "md": "wss://md.tradovateapi.com/v1/websocket",
        "ws": "wss://live.tradovateapi.com/v1/websocket",
    },
}


class StrategyParams(BaseSettings):
    """Mirrors the Pine Script inputs. Mutable at runtime via the dashboard."""

    model_config = SettingsConfigDict(env_prefix="STRATEGY_", extra="ignore")

    timezone: str = "America/Los_Angeles"
    session: str = "0630-1300"          # PT session window, HHMM-HHMM
    or_candles: int = 3                 # opening-range candle count
    departure_pts: float = 15.0         # min run past level before retest counts
    confirm_close: bool = True          # retest must close back beyond the level
    stop_pts: float = 50.0
    tp_pts: float = 100.0
    one_trade: bool = True              # one trade per day
    use_vwap: bool = True               # long only above VWAP, short below
    use_partial: bool = True            # scale out at +1R and move stop to BE
    partial_pct: int = 50


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Tradovate
    tradovate_env: str = "demo"
    tradovate_username: str = ""
    tradovate_password: str = ""
    tradovate_app_id: str = "YN Finance ORB Bot"
    tradovate_app_version: str = "1.0"
    tradovate_cid: str = ""
    tradovate_secret: str = ""
    tradovate_device_id: str = "yn-orb-bot-device-01"
    tradovate_account_spec: str = ""
    tradovate_account_id: int = 0

    # Instrument
    symbol: str = "MNQM5"
    point_value: float = 2.0
    quantity: int = 1

    # Execution
    auto_trade: bool = False
    # Which broker route to execute through: "tradovate" (direct API key) or
    # "traderspost" (webhook bridge — works with Lucid and other prop firms
    # without a broker API key).
    broker: str = "tradovate"
    traderspost_webhook_url: str = ""
    # Ticker as your TradersPost broker connection expects it (futures often
    # differ from the Tradovate symbol). Falls back to SYMBOL if blank.
    traderspost_ticker: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite:///./data/orb_bot.sqlite"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    strategy: StrategyParams = Field(default_factory=StrategyParams)

    @property
    def hosts(self) -> dict[str, str]:
        return TRADOVATE_HOSTS[self.tradovate_env if self.tradovate_env in TRADOVATE_HOSTS else "demo"]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def credentials_present(self) -> bool:
        return bool(self.tradovate_username and self.tradovate_password and self.tradovate_cid)

    @property
    def exec_ticker(self) -> str:
        return self.traderspost_ticker or self.symbol

    @property
    def execution_ready(self) -> bool:
        """Whether the chosen execution route is configured."""
        if self.broker == "traderspost":
            return bool(self.traderspost_webhook_url)
        return self.credentials_present


@lru_cache
def get_settings() -> Settings:
    return Settings()
