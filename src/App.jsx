import React, { useEffect, useMemo, useState } from 'react'
import { AssetTable } from './components/AssetTable.jsx'
import { MiniChart } from './components/MiniChart.jsx'
import { LessonPane } from './components/LessonPane.jsx'
import { loadAllData } from './lib/data.js'

const STOCKS = ['AAPL','MSFT','AMZN','GOOGL','META','NVDA','TSLA','AMD','NFLX','JPM','BAC','XOM','V','JNJ','AVGO']
const CRYPTO = ['bitcoin','ethereum','binancecoin','solana','ripple','dogecoin','cardano','toncoin','tron','polkadot','litecoin','chainlink','avalanche-2','matic-network','shiba-inu']
const FOREX = ['EURUSD','USDJPY','GBPUSD','AUDUSD','USDCAD','USDCHF','USDCNY','USDINR','USDMXN','USDBRL','USDKRW','NZDUSD','USDSEK','USDNOK','USDPLN']
const FUTURES = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOGEUSDT','DOTUSDT','LTCUSDT','LINKUSDT','AVAXUSDT','MATICUSDT','TRXUSDT','TONUSDT','SHIBUSDT']

const TABS = [
  { key:'stocks', label:'Stocks', list: STOCKS },
  { key:'crypto', label:'Crypto', list: CRYPTO },
  { key:'forex', label:'Forex', list: FOREX },
  { key:'futures', label:'Futures (Binance)', list: FUTURES },
]

export default function App(){
  const [tab, setTab] = useState('stocks')
  const [data, setData] = useState({})
  const [selected, setSelected] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  // poll every 15s
  useEffect(()=>{
    let mounted = true
    const tick = async ()=>{
      const apiKey = import.meta.env.VITE_FINNHUB_KEY || ''
      const d = await loadAllData({ apiKey, STOCKS, CRYPTO, FOREX, FUTURES })
      if(mounted){
        setData(d)
        setLastUpdated(new Date())
        if(!selected){
          const first = TABS.find(t=>t.key===tab).list[0]
          setSelected(first)
        }
      }
    }
    tick()
    const id = setInterval(tick, 15000)
    return ()=>{ mounted=false; clearInterval(id) }
  },[tab])

  const currentList = useMemo(()=> {
    const list = TABS.find(t=>t.key===tab).list
    return list.map(sym=> data[sym]).filter(Boolean)
  },[data, tab])

  return (
    <div>
      <header className="header card">
        <div className="brand">
          <div className="logo">KV</div>
          <div>
            <div style={{fontWeight:800}}>Kidvestor</div>
            <div className="small">Learn • Play • Paper Trade</div>
          </div>
        </div>
        <div className="small">Updates every 15s {lastUpdated ? `• Last: ${lastUpdated.toLocaleTimeString()}` : ''}</div>
      </header>

      <main className="grid" style={{padding:'16px'}}>
        <section className="card">
          <div className="tabs">
            {TABS.map(t=>(
              <div key={t.key} className={'tab '+(t.key===tab?'active':'')} onClick={()=>{setTab(t.key); setSelected(null)}}>{t.label}</div>
            ))}
            <span className="badge">Top 15</span>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'1fr', gap:'16px'}}>
            <MiniChart selected={selected} data={data} tab={tab}/>
            <AssetTable rows={currentList} onSelect={setSelected}/>
          </div>
        </section>

        <aside className="card">
          <LessonPane />
        </aside>
      </main>

      <footer style={{padding:'16px', textAlign:'center'}} className="small">
        © Kidvestor. Educational only. No real money. Protect your privacy.
      </footer>
    </div>
  )
}
