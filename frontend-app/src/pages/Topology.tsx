import { useEffect, useState } from 'react'
import { apiGet } from '../api'

type Segment = { id_segmentu:number; nazwa_segmentu:string; nazwa_zaworu:string; punkt_startowy:string; punkt_koncowy:string; zajety?:boolean }

export default function Topology() {
  const [segments, setSegments] = useState<Segment[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try { setSegments(await apiGet('/api/topologia')) } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  return (
    <div className="space-y-3">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}
      <div className="flex justify-between items-center">
        <h2 className="font-bold text-lg">Segmenty</h2>
        <button className="px-3 py-1 bg-cyan-700 rounded" onClick={load}>Odśwież</button>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {segments.map(s=>(
          <div key={s.id_segmentu} className={`rounded p-3 ${s.zajety ? 'bg-red-900/40 border border-red-700' : 'bg-slate-800'}`}>
            <div className="font-semibold">{s.nazwa_segmentu}</div>
            <div className="text-xs">Zawór: {s.nazwa_zaworu}</div>
            <div className="text-xs">{s.punkt_startowy} → {s.punkt_koncowy}</div>
            {s.zajety && <div className="text-xs text-red-300 mt-1">Zajęty</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

