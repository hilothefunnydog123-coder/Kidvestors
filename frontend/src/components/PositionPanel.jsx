import React from 'react'

const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toFixed(d))

export default function PositionPanel({ state }) {
  const s = state || {}
  const pos = s.position
  const ss = s.strategy_state || {}
  const bar = s.last_bar

  return (
    <div className="card">
      <h3>Live position & range</h3>

      {pos ? (
        <div>
          <div className="pos-line">
            <span>Side</span>
            <span className={`tag ${pos.side === 'LONG' ? 'long' : 'short'}`}>{pos.side}</span>
          </div>
          <div className="pos-line"><span className="muted">Entry</span><span>{fmt(pos.entry)}</span></div>
          <div className="pos-line"><span className="muted">Stop</span><span className="red">{fmt(pos.be_moved ? pos.entry : pos.stop)}{pos.be_moved ? ' (BE)' : ''}</span></div>
          <div className="pos-line"><span className="muted">Target</span><span className="green">{fmt(pos.target)}</span></div>
          <div className="pos-line"><span className="muted">+1R level</span><span>{fmt(pos.r1)}{pos.scaled ? ' ✓ scaled' : ''}</span></div>
          <div className="pos-line"><span className="muted">Qty</span><span>{pos.qty}</span></div>
        </div>
      ) : (
        <div className="empty">No open position</div>
      )}

      <div style={{ marginTop: 14 }}>
        <div className="pos-line"><span className="muted">OR High</span><span>{fmt(ss.or_high)}</span></div>
        <div className="pos-line"><span className="muted">OR Low</span><span>{fmt(ss.or_low)}</span></div>
        <div className="pos-line"><span className="muted">VWAP</span><span>{fmt(ss.vwap)}</span></div>
        <div className="pos-line">
          <span className="muted">Setup</span>
          <span>
            {ss.long_valid ? <span className="green">long armed </span> : null}
            {ss.short_valid ? <span className="red">short armed</span> : null}
            {!ss.long_valid && !ss.short_valid ? (ss.or_done ? 'watching' : 'building range') : null}
          </span>
        </div>
        <div className="pos-line"><span className="muted">Traded today</span><span>{ss.traded_today ? 'yes' : 'no'}</span></div>
        {bar && (
          <div className="pos-line"><span className="muted">Last close</span><span>{fmt(bar.close)}</span></div>
        )}
      </div>
    </div>
  )
}
