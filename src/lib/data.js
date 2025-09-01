// Data loader for Kidvestor
// Sources:
// - Stocks: Finnhub /quote (needs VITE_FINNHUB_KEY)
// - Crypto: CoinGecko simple price (no key)
// - Forex: exchangerate.host latest (no key) -> convert to pairs
// - Futures: Binance Futures public API (no key)

export async function loadAllData({ apiKey, STOCKS, CRYPTO, FOREX, FUTURES }){
  const [stocks, crypto, forex, futures] = await Promise.all([
    loadStocks(STOCKS, apiKey).catch(()=>({})),
    loadCrypto(CRYPTO).catch(()=>({})),
    loadForex(FOREX).catch(()=>({})),
    loadFutures(FUTURES).catch(()=>({})),
  ])
  return { ...stocks, ...crypto, ...forex, ...futures }
}

async function loadStocks(symbols, key){
  const out = {}
  const base = 'https://finnhub.io/api/v1/quote'
  const now = Date.now()
  await Promise.all(symbols.map(async sym=>{
    const url = `${base}?symbol=${encodeURIComponent(sym)}&token=${encodeURIComponent(key)}`
    const r = await fetch(url)
    if(!r.ok) throw new Error('stocks fetch failed')
    const q = await r.json() // { c: current, d: change, dp: percent, h, l, o, pc }
    out[sym] = toRow({ symbol: sym, price: q.c, change: q.dp, source:'Finnhub', now })
  }))
  return out
}

async function loadCrypto(ids){
  const out = {}
  const base = 'https://api.coingecko.com/api/v3/simple/price'
  const url = `${base}?ids=${ids.join(',')}&vs_currencies=usd&include_24hr_change=true`
  const r = await fetch(url)
  const j = await r.json()
  const now = Date.now()
  for(const id of ids){
    const obj = j[id]
    if(!obj) continue
    const sym = id.toUpperCase().replace(/-2|\-POS|\-NETWORK/g,'')
    out[id] = toRow({ symbol: sym, price: obj.usd, change: obj.usd_24h_change, source:'CoinGecko', now })
  }
  return out
}

async function loadForex(pairs){
  const out = {}
  // We'll fetch USD base and compute major pairs; for EURUSD we need USD->EUR invert if base != desired
  const url = 'https://api.exchangerate.host/latest?base=USD'
  const r = await fetch(url)
  const j = await r.json()
  const now = Date.now()
  for(const pair of pairs){
    const a = pair.slice(0,3)
    const b = pair.slice(3,6)
    let price = null
    if(a === 'USD'){
      price = j.rates[b]
    } else if(b === 'USD'){
      // need inverse of USD->A
      const usdToA = j.rates[a]
      price = 1 / usdToA
    } else {
      // cross rate: A/B = (USD/B) / (USD/A)
      price = j.rates[b] / j.rates[a]
    }
    out[pair] = toRow({ symbol: pair, price, change: 0, source:'exchangerate.host', now })
  }
  return out
}

async function loadFutures(symbols){
  const out = {}
  const now = Date.now()
  await Promise.all(symbols.map(async sym=>{
    const url = `https://fapi.binance.com/fapi/v1/ticker/price?symbol=${sym}`
    const r = await fetch(url)
    const j = await r.json()
    out[sym] = toRow({ symbol: sym, price: Number(j.price), change: 0, source:'Binance Futures', now })
  }))
  return out
}

function toRow({ symbol, price, change, source, now }){
  const prev = getHistory(symbol)
  const last = prev.at(-1)?.p ?? price
  const pct = (price && last) ? ((price - last) / last) * 100 : (change ?? 0)
  const row = { symbol, price, change: change ?? pct, source, history: [...prev, { t: now, p: price }].slice(-120) }
  setHistory(symbol, row.history)
  return row
}

function getHistory(key){
  try{
    const raw = localStorage.getItem('kv_hist_'+key)
    return raw ? JSON.parse(raw) : []
  }catch{ return [] }
}
function setHistory(key, arr){
  try{
    localStorage.setItem('kv_hist_'+key, JSON.stringify(arr))
  }catch{}
}
