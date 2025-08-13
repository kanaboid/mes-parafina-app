import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'

export default function Monitoring() {
  const [parametry, setParametry] = useState<any[]>([])
  const [alArmy, setAlArmy] = useState<any[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try {
      setParametry(await apiGet('/api/monitoring/parametry'))
      setAlArmy(await apiGet('/api/monitoring/alarmy-parametryczne'))
    } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  async function forceRead() { try { await apiPost('/api/test/sensors', {}); setMsg('Odczyt czujników OK') } catch(e:any){ setMsg(e.message) } }
  async function forceAlarm() {
    const sprzet_id = prompt('ID sprzętu do wymuszenia alarmu?')
    const typ_alarmu = prompt('typ_alarmu: temperatura | cisnienie')
    if (!sprzet_id || !typ_alarmu) return
    try { await apiPost('/api/test/alarm', { sprzet_id:+sprzet_id, typ_alarmu }); setMsg('Alarm wymuszony') } catch(e:any){ setMsg(e.message) }
  }

  async function potwierdzAlarm(id:number){
    try { await apiPost('/api/alarmy/potwierdz', { id_alarmu:id }); setMsg('Potwierdzono alarm'); load() } catch(e:any){ setMsg(e.message) }
  }

  return (
    <div className="space-y-6">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}
      <div className="flex gap-2">
        <button className="px-3 py-1 bg-cyan-700 rounded" onClick={load}>Odśwież</button>
        <button className="px-3 py-1 bg-slate-700 rounded" onClick={forceRead}>Wymuś odczyt</button>
        <button className="px-3 py-1 bg-red-700 rounded" onClick={forceAlarm}>Wymuś alarm</button>
      </div>

      <section>
        <h2 className="font-bold text-lg mb-2">Parametry</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {parametry.map(p=> (
            <div key={p.id} className="bg-slate-800 rounded p-3">
              <div className="font-semibold">{p.nazwa_unikalna} <span className="text-xs text-slate-400">({p.typ_sprzetu})</span></div>
              <div className="text-xs">Temp: {p.temperatura_aktualna} / Max: {p.temperatura_max}</div>
              <div className="text-xs">Ciśn: {p.cisnienie_aktualne} / Max: {p.cisnienie_max}</div>
              <div className="text-xs">Status: {p.status_parametrow} ({p.status_danych})</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-bold text-lg mb-2">Alarmy parametryczne</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {alArmy.map(a=> (
            <div key={a.id} className="bg-slate-800 rounded p-3 flex items-center justify-between">
              <div>
                <div className="font-semibold">{a.nazwa_unikalna}</div>
                <div className="text-xs">{a.typ_alarmu} przekroczenie: {a.przekroczenie_wartosci}</div>
              </div>
              <button className="px-3 py-1 bg-emerald-700 rounded" onClick={()=>potwierdzAlarm(a.id)}>Potwierdź</button>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

