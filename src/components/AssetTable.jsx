import React from 'react'

export function AssetTable({ rows = [], onSelect }){
  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Δ</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r=>(
            <tr key={r.symbol} onClick={()=>onSelect && onSelect(r.symbol)} style={{cursor:'pointer'}}>
              <td>{r.symbol}</td>
              <td>{formatPrice(r.price)}</td>
              <td className={r.change>=0?'green':'red'}>{formatDelta(r.change)}</td>
              <td className="small">{r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length===0 && <div className="small">Loading…</div>}
    </div>
  )
}

function formatPrice(p){
  if(p === null || p === undefined) return '-'
  const n = Number(p)
  if(n >= 1000) return n.toLocaleString(undefined, {maximumFractionDigits:2})
  return n.toFixed(2)
}
function formatDelta(d){
  if(d === null || d === undefined) return '-'
  const sign = d>0?'+':''
  return sign + d.toFixed(2) + '%'
}
