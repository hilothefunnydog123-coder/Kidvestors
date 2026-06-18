import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, wsUrl } from './api.js'
import TopBar from './components/TopBar.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import PositionPanel from './components/PositionPanel.jsx'
import StrategyConfig from './components/StrategyConfig.jsx'
import Analytics from './components/Analytics.jsx'
import EquityCurve from './components/EquityCurve.jsx'
import TradeLog from './components/TradeLog.jsx'

export default function App() {
  const [state, setState] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [trades, setTrades] = useState([])
  const [online, setOnline] = useState(false)
  const wsRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const [a, t] = await Promise.all([api.analytics(), api.trades()])
      setAnalytics(a)
      setTrades(t)
    } catch { /* backend down */ }
  }, [])

  useEffect(() => {
    api.state().then(setState).catch(() => {})
    refresh()
  }, [refresh])

  // Live WebSocket with auto-reconnect
  useEffect(() => {
    let stop = false
    let timer
    const connect = () => {
      const ws = new WebSocket(wsUrl())
      wsRef.current = ws
      ws.onopen = () => setOnline(true)
      ws.onclose = () => {
        setOnline(false)
        if (!stop) timer = setTimeout(connect, 2000)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'state') setState(msg.data)
        if (msg.type === 'trade_closed' || msg.type === 'signal' || msg.type === 'scale') {
          refresh()
        }
      }
    }
    connect()
    return () => { stop = true; clearTimeout(timer); wsRef.current?.close() }
  }, [refresh])

  // Periodic analytics refresh as a safety net
  useEffect(() => {
    const id = setInterval(refresh, 15000)
    return () => clearInterval(id)
  }, [refresh])

  const backendDown = state === null && !online

  return (
    <div className="app">
      <TopBar state={state} />

      {backendDown && (
        <div className="banner error">
          Can't reach the backend at <code>{import.meta.env.VITE_API_BASE || 'http://localhost:8000'}</code>.
          Start it with <code>uvicorn app.main:app --port 8000</code> in <code>backend/</code>.
        </div>
      )}
      {state && !state.credentials_present && (
        <div className="banner warn">
          Tradovate credentials missing — fill in <code>backend/.env</code> to connect.
          You can still configure the strategy and run backtests.
        </div>
      )}
      {state?.last_error && (
        <div className="banner error">{state.last_error}</div>
      )}

      <div className="grid">
        <div className="col-3"><ControlPanel state={state} api={api} /></div>
        <div className="col-3"><PositionPanel state={state} /></div>
        <div className="col-6"><Analytics analytics={analytics} /></div>

        <div className="col-8"><EquityCurve analytics={analytics} /></div>
        <div className="col-4" style={{ gridRow: 'span 2' }}><StrategyConfig api={api} /></div>

        <div className="col-8"><TradeLog trades={trades} api={api} onChange={refresh} /></div>
      </div>

      <div className="muted" style={{ textAlign: 'center', marginTop: 18, fontSize: 12 }}>
        For your own account only · Not financial advice · Trades real money when auto-trade is ON in live mode
      </div>
    </div>
  )
}
