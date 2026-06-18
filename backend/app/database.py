"""SQLite persistence for signals, trades, and the equity curve."""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    side = Column(String)                 # LONG / SHORT
    entry = Column(Float)
    stop = Column(Float)
    target = Column(Float)
    r1 = Column(Float)                    # +1R scale-out level
    qty = Column(Integer)

    opened_at = Column(DateTime, default=_utcnow)
    closed_at = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    outcome = Column(String, nullable=True)   # TARGET / STOP / BREAKEVEN / OPEN
    pnl = Column(Float, nullable=True)        # $ realized
    r_multiple = Column(Float, nullable=True)
    be_moved = Column(Boolean, default=False)
    scaled = Column(Boolean, default=False)
    live = Column(Boolean, default=False)     # real order vs signals-only
    note = Column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "r1": self.r1,
            "qty": self.qty,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "exit_price": self.exit_price,
            "outcome": self.outcome,
            "pnl": self.pnl,
            "r_multiple": self.r_multiple,
            "be_moved": self.be_moved,
            "scaled": self.scaled,
            "live": self.live,
            "note": self.note,
        }


_engine = None
_Session = None


def init_db():
    global _engine, _Session
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    _engine = create_engine(url, connect_args={"check_same_thread": False})
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)


@contextmanager
def session_scope():
    if _Session is None:
        init_db()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
