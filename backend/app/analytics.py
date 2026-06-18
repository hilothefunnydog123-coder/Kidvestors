"""Performance analytics computed from the closed-trade history."""
from __future__ import annotations

from datetime import datetime

from .database import Trade, session_scope


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute_analytics() -> dict:
    with session_scope() as s:
        trades = s.query(Trade).order_by(Trade.opened_at.asc()).all()
        closed = [t for t in trades if t.outcome and t.outcome != "OPEN" and t.pnl is not None]

        total = len(closed)
        wins = [t for t in closed if (t.pnl or 0) > 0]
        losses = [t for t in closed if (t.pnl or 0) < 0]
        scratches = [t for t in closed if (t.pnl or 0) == 0]

        gross_win = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        net = sum(t.pnl for t in closed)

        r_values = [t.r_multiple for t in closed if t.r_multiple is not None]
        avg_r = _safe_div(sum(r_values), len(r_values)) if r_values else 0.0

        win_rate = _safe_div(len(wins), total) * 100 if total else 0.0
        avg_win = _safe_div(gross_win, len(wins)) if wins else 0.0
        avg_loss = _safe_div(gross_loss, len(losses)) if losses else 0.0
        profit_factor = _safe_div(gross_win, gross_loss) if gross_loss else (gross_win and float("inf") or 0.0)
        expectancy = _safe_div(net, total) if total else 0.0

        # Equity curve + drawdown
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        curve = []
        for t in closed:
            equity += t.pnl or 0.0
            peak = max(peak, equity)
            max_dd = min(max_dd, equity - peak)
            curve.append({
                "t": (t.closed_at or t.opened_at).isoformat() if (t.closed_at or t.opened_at) else None,
                "equity": round(equity, 2),
                "pnl": round(t.pnl or 0.0, 2),
            })

        # Streaks
        cur_streak = 0
        best_win_streak = 0
        worst_loss_streak = 0
        for t in closed:
            p = t.pnl or 0
            if p > 0:
                cur_streak = cur_streak + 1 if cur_streak > 0 else 1
                best_win_streak = max(best_win_streak, cur_streak)
            elif p < 0:
                cur_streak = cur_streak - 1 if cur_streak < 0 else -1
                worst_loss_streak = min(worst_loss_streak, cur_streak)
            else:
                cur_streak = 0

        return {
            "total_trades": total,
            "open_trades": sum(1 for t in trades if t.outcome == "OPEN"),
            "wins": len(wins),
            "losses": len(losses),
            "scratches": len(scratches),
            "win_rate": round(win_rate, 2),
            "net_pnl": round(net, 2),
            "gross_profit": round(gross_win, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else None,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_r": round(avg_r, 3),
            "expectancy": round(expectancy, 2),
            "max_drawdown": round(max_dd, 2),
            "best_win_streak": best_win_streak,
            "worst_loss_streak": abs(worst_loss_streak),
            "equity_curve": curve,
        }
