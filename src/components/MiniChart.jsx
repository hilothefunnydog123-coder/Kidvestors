import React, { useEffect, useMemo, useRef } from 'react'
import { createChart } from 'lightweight-charts'

export function MiniChart({ selected, data, tab }){
  const ref = useRef()
  const seriesRef = useRef()
  const chartRef = useRef()

  const points = useMemo(()=>{
    const sym = selected
    if(!sym) return []
    const r = data[sym]
    if(!r) return []
    return r.history || []
  }, [selected, data])

  useEffect(()=>{
    if(!ref.current) return
    if(chartRef.current) return
    const chart = createChart(ref.current, { width: 700, height: 280, layout: { background: { color: '#121a36' }, textColor: '#e8ebff' }, grid: { vertLines: { color: '#223060' }, horzLines: { color: '#223060' } } })
    const line = chart.addLineSeries({ color: '#49e689', lineWidth: 2 })
    chartRef.current = chart
    seriesRef.current = line
    const ro = new ResizeObserver(entries=>{
      for(const e of entries){
        chart.applyOptions({ width: e.contentRect.width })
      }
    })
    ro.observe(ref.current)
    return ()=>{ ro.disconnect(); chart.remove(); chartRef.current=null; seriesRef.current=null }
  },[])

  useEffect(()=>{
    if(seriesRef.current){
      const mapped = points.map(p=>({ time: Math.floor(p.t/1000), value: Number(p.p) }))
      seriesRef.current.setData(mapped)
    }
  },[points])

  return (
    <div>
      <div className="small" style={{marginBottom:'6px'}}>Selected: {selected || '—'}</div>
      <div ref={ref} className="card" style={{padding:'0', height:'300px'}} />
    </div>
  )
}
