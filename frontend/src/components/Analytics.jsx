import React from 'react'

const Metric = ({ label, value, cls }) => (
  <div className="metric">
    <span className="label">{label}</span>
    <span className={`value ${cls || ''}`}>{value}</span>
  </div>
)

const money = (v) => (v == null ? '—' : `${v < 0 ? '-' : ''}$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)

export default function Analytics({ analytics }) {
  const a = analytics || {}
  const pnlCls = (a.net_pnl || 0) >= 0 ? 'green' : 'red'

  return (
    <div className="card">
      <h3>Performance analytics</h3>
      <div className="metrics-grid">
        <Metric label="Net P&L" value={money(a.net_pnl)} cls={pnlCls} />
        <Metric label="Win rate" value={a.total_trades ? `${a.win_rate}%` : '—'} />
        <Metric label="Trades" value={a.total_trades ?? 0} />
        <Metric label="Expectancy" value={money(a.expectancy)} />
        <Metric label="Profit factor" value={a.profit_factor ?? '—'} />
        <Metric label="Avg R" value={a.avg_r ?? '—'} />
        <Metric label="Avg win" value={money(a.avg_win)} cls="green" />
        <Metric label="Avg loss" value={money(a.avg_loss ? -a.avg_loss : 0)} cls="red" />
        <Metric label="Max drawdown" value={money(a.max_drawdown)} cls="red" />
        <Metric label="Win streak" value={a.best_win_streak ?? 0} />
        <Metric label="Loss streak" value={a.worst_loss_streak ?? 0} />
        <Metric label="Open" value={a.open_trades ?? 0} />
      </div>
    </div>
  )
}
