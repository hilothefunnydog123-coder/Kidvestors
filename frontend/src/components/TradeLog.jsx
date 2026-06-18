import React from 'react'

const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toFixed(d))
const money = (v) => (v == null ? '—' : `${v < 0 ? '-' : ''}$${Math.abs(v).toFixed(2)}`)

const outcomeCls = (o) => {
  if (o === 'TARGET') return 'green'
  if (o === 'STOP') return 'red'
  if (o === 'OPEN') return 'muted'
  return ''
}

export default function TradeLog({ trades, api, onChange }) {
  const rows = trades || []

  const clear = async () => {
    if (!confirm('Clear all trade history?')) return
    await api.clearTrades()
    onChange?.()
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Trade log</h3>
        <button className="btn ghost" onClick={clear}>Clear</button>
      </div>
      {rows.length === 0 ? (
        <div className="empty">No trades recorded yet</div>
      ) : (
        <div style={{ overflowX: 'auto', marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>Time</th><th>Side</th><th>Entry</th><th>Stop</th><th>Target</th>
                <th>Exit</th><th>Outcome</th><th>R</th><th>P&L</th><th>Mode</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id}>
                  <td>{t.opened_at ? new Date(t.opened_at).toLocaleString() : '—'}</td>
                  <td><span className={`tag ${t.side === 'LONG' ? 'long' : 'short'}`}>{t.side}</span></td>
                  <td>{fmt(t.entry)}</td>
                  <td>{fmt(t.be_moved ? t.entry : t.stop)}</td>
                  <td>{fmt(t.target)}</td>
                  <td>{fmt(t.exit_price)}</td>
                  <td className={outcomeCls(t.outcome)}>{t.outcome}</td>
                  <td className={(t.r_multiple || 0) >= 0 ? 'green' : 'red'}>{t.r_multiple ?? '—'}</td>
                  <td className={(t.pnl || 0) >= 0 ? 'green' : 'red'}>{money(t.pnl)}</td>
                  <td className="muted">{t.live ? 'live' : 'sim'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
