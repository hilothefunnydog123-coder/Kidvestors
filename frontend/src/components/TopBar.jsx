import React from 'react'

const connDot = (c) => {
  if (c === 'streaming') return 'on'
  if (c === 'connecting') return 'warn'
  return 'off'
}

export default function TopBar({ state }) {
  const s = state || {}
  const env = s.env || 'demo'
  return (
    <div className="topbar">
      <div className="brand">
        <div className="logo">YN</div>
        <div>
          <h1>YN Finance — 6:30 ORB Retest Bot</h1>
          <div className="sub">Algorithmic auto-trader · Tradovate</div>
        </div>
      </div>
      <div className="pills">
        <span className={`pill ${env === 'live' ? 'live' : 'demo'}`}>
          {env === 'live' ? '🔴 LIVE' : '🧪 DEMO'}
        </span>
        <span className="pill">
          <span className={`dot ${connDot(s.connection)}`} />
          {s.connection || 'disconnected'}
        </span>
        <span className="pill">
          <span className={`dot ${s.auto_trade ? 'on' : 'off'}`} />
          {s.auto_trade ? 'auto-trade ON' : 'signals only'}
        </span>
        <span className="pill">{s.symbol || '—'}</span>
      </div>
    </div>
  )
}
