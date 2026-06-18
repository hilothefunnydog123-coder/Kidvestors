import React, { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

export default function EquityCurve({ analytics }) {
  const ref = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = createChart(ref.current, {
      layout: { background: { color: 'transparent' }, textColor: '#8a98bd' },
      grid: { vertLines: { color: '#20304f33' }, horzLines: { color: '#20304f33' } },
      rightPriceScale: { borderColor: '#20304f' },
      timeScale: { borderColor: '#20304f' },
      height: 260,
    })
    const series = chart.addAreaSeries({
      lineColor: '#5b8cff', topColor: '#5b8cff44', bottomColor: '#5b8cff00', lineWidth: 2,
    })
    chartRef.current = chart
    seriesRef.current = series
    const onResize = () => chart.applyOptions({ width: ref.current.clientWidth })
    onResize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.remove() }
  }, [])

  useEffect(() => {
    const curve = analytics?.equity_curve || []
    if (!seriesRef.current) return
    const data = curve.map((p, i) => ({
      time: Math.floor(new Date(p.t).getTime() / 1000) || i,
      value: p.equity,
    }))
    // lightweight-charts needs strictly increasing unique times
    const seen = new Set()
    const clean = []
    for (const d of data) {
      let t = d.time
      while (seen.has(t)) t += 1
      seen.add(t)
      clean.push({ time: t, value: d.value })
    }
    seriesRef.current.setData(clean)
    if (clean.length) chartRef.current.timeScale().fitContent()
  }, [analytics])

  return (
    <div className="card">
      <h3>Equity curve</h3>
      {(analytics?.equity_curve?.length || 0) === 0 ? (
        <div className="empty">No closed trades yet</div>
      ) : (
        <div className="chart-wrap" ref={ref} />
      )}
    </div>
  )
}
