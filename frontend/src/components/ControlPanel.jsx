import React, { useState } from 'react'

export default function ControlPanel({ state, api }) {
  const [busy, setBusy] = useState(false)
  const s = state || {}

  const run = async (fn) => {
    setBusy(true)
    try { await fn() } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  const cash = s.cash || {}
  const balance = cash.totalCashValue ?? cash.amount ?? null

  return (
    <div className="card">
      <h3>Control</h3>
      <div className="row" style={{ marginBottom: 14 }}>
        {!s.running ? (
          <button className="btn primary" disabled={busy} onClick={() => run(api.start)}>
            ▶ Start bot
          </button>
        ) : (
          <button className="btn" disabled={busy} onClick={() => run(api.stop)}>
            ⏸ Stop bot
          </button>
        )}
        <button className="btn danger" disabled={busy} onClick={() => run(api.kill)}>
          ⛔ Kill / Flatten
        </button>
      </div>

      <div className="toggle">
        <div>
          <div>Auto-trade (send real orders)</div>
          <div className="muted" style={{ fontSize: 11 }}>
            Off = signals logged only, no orders sent
          </div>
        </div>
        <label className="switch">
          <input
            type="checkbox"
            checked={!!s.auto_trade}
            onChange={(e) => run(() => api.setAutoTrade(e.target.checked))}
          />
          <span className="slider" />
        </label>
      </div>

      <div style={{ marginTop: 14 }}>
        <div className="pos-line">
          <span className="muted">Account</span>
          <span>{s.account?.name || '—'}</span>
        </div>
        <div className="pos-line">
          <span className="muted">Balance</span>
          <span>{balance != null ? `$${Number(balance).toLocaleString()}` : '—'}</span>
        </div>
        <div className="pos-line">
          <span className="muted">Credentials</span>
          <span className={s.credentials_present ? 'green' : 'red'}>
            {s.credentials_present ? 'configured' : 'missing (.env)'}
          </span>
        </div>
      </div>
    </div>
  )
}
