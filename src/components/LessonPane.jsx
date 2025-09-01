import React, { useEffect, useState } from 'react'

const LESSONS = [
  { id:1, title:'What is a Stock?', reward:'Unlock Line Chart' },
  { id:2, title:'Reading a Ticker', reward:'Unlock % Change' },
  { id:3, title:'What is Crypto?', reward:'Unlock Crypto Tab' },
  { id:4, title:'What is Forex?', reward:'Unlock Forex Tab' },
  { id:5, title:'Trends & Candles', reward:'Unlock Candles (coming soon)' },
  { id:6, title:'Risk Basics', reward:'Badge: Risk Aware' },
]

export function LessonPane(){
  const [progress,setProgress] = useState(()=>JSON.parse(localStorage.getItem('kv_progress')||'[]'))

  useEffect(()=>{ localStorage.setItem('kv_progress', JSON.stringify(progress)) },[progress])

  function toggle(id){
    setProgress(p=> p.includes(id) ? p.filter(x=>x!==id) : [...p, id])
  }

  return (
    <div>
      <h3 style={{marginTop:0}}>Lessons & Unlocks</h3>
      <ul style={{listStyle:'none', padding:0, margin:0}}>
        {LESSONS.map(l=>(
          <li key={l.id} className="card" style={{marginBottom:'8px'}}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
              <div>
                <div style={{fontWeight:700}}>{l.title}</div>
                <div className="small">Reward: {l.reward}</div>
              </div>
              <button className="btn" onClick={()=>toggle(l.id)}>{progress.includes(l.id)?'Completed ✓':'Mark Complete'}</button>
            </div>
          </li>
        ))}
      </ul>
      <div className="small" style={{marginTop:'8px'}}>Your progress is saved on this device only.</div>
    </div>
  )
}
