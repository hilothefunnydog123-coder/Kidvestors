import React, { useEffect, useState } from 'react'

const NUMS = [
  ['or_candles', 'Opening-range candles', 1],
  ['departure_pts', 'Min run past level (pts)', 0.5],
  ['stop_pts', 'Stop (pts)', 1],
  ['tp_pts', 'Target (pts)', 1],
  ['partial_pct', 'Scale-out at +1R (%)', 1],
]
const BOOLS = [
  ['confirm_close', 'Retest must close back beyond level'],
  ['use_vwap', 'VWAP filter (long above / short below)'],
  ['use_partial', 'Scale out at +1R → breakeven'],
  ['one_trade', 'One trade per day'],
]

export default function StrategyConfig({ api }) {
  const [cfg, setCfg] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.config().then((c) => setCfg(c.strategy)).catch(() => {})
  }, [])

  if (!cfg) return <div className="card"><h3>Strategy</h3><div className="empty">loading…</div></div>

  const set = (k, v) => { setCfg({ ...cfg, [k]: v }); setSaved(false) }

  const save = async () => {
    setSaving(true)
    try {
      await api.updateStrategy({
        or_candles: Number(cfg.or_candles),
        departure_pts: Number(cfg.departure_pts),
        stop_pts: Number(cfg.stop_pts),
        tp_pts: Number(cfg.tp_pts),
        partial_pct: Number(cfg.partial_pct),
        confirm_close: !!cfg.confirm_close,
        use_vwap: !!cfg.use_vwap,
        use_partial: !!cfg.use_partial,
        one_trade: !!cfg.one_trade,
        session: cfg.session,
      })
      setSaved(true)
    } catch (e) { alert(e.message) } finally { setSaving(false) }
  }

  return (
    <div className="card">
      <h3>Strategy parameters</h3>

      <div className="field">
        <label>Trading session (PT, HHMM-HHMM)</label>
        <input type="text" value={cfg.session} onChange={(e) => set('session', e.target.value)} />
      </div>

      {NUMS.map(([k, label, step]) => (
        <div className="field" key={k}>
          <label>{label}</label>
          <input type="number" step={step} value={cfg[k]} onChange={(e) => set(k, e.target.value)} />
        </div>
      ))}

      {BOOLS.map(([k, label]) => (
        <div className="toggle" key={k}>
          <div style={{ fontSize: 13 }}>{label}</div>
          <label className="switch">
            <input type="checkbox" checked={!!cfg[k]} onChange={(e) => set(k, e.target.checked)} />
            <span className="slider" />
          </label>
        </div>
      ))}

      <button className="btn primary" style={{ marginTop: 12, width: '100%' }} disabled={saving} onClick={save}>
        {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Apply parameters'}
      </button>
    </div>
  )
}
