const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

export const api = {
  state: () => req('/api/state'),
  config: () => req('/api/config'),
  trades: () => req('/api/trades'),
  analytics: () => req('/api/analytics'),
  start: () => req('/api/bot/start', { method: 'POST' }),
  stop: () => req('/api/bot/stop', { method: 'POST' }),
  kill: () => req('/api/bot/kill', { method: 'POST' }),
  setAutoTrade: (enabled) =>
    req('/api/bot/auto-trade', { method: 'POST', body: JSON.stringify({ enabled }) }),
  updateStrategy: (params) =>
    req('/api/strategy', { method: 'POST', body: JSON.stringify(params) }),
  clearTrades: () => req('/api/trades', { method: 'DELETE' }),
}

export function wsUrl() {
  return BASE.replace(/^http/, 'ws') + '/ws'
}
