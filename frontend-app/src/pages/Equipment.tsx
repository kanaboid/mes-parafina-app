import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'

type Sprzet = { id:number; nazwa_unikalna:string; typ_sprzetu:string; stan_sprzetu:string; id_partii?:number|null; unikalny_kod?:string|null }
type Zawor = { id:number; nazwa_zaworu:string; stan:'OTWARTY'|'ZAMKNIETY' }

export default function Equipment() {
  const [sprzet, setSprzet] = useState<Sprzet[]>([])
  const [zawory, setZawory] = useState<Zawor[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try {
      setSprzet(await apiGet('/api/sprzet'))
      setZawory(await apiGet('/api/zawory'))
    } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  async function zmienStan(id:number, stan:string) {
    try { await apiPost('/api/zawory/zmien_stan', { id_zaworu:id, stan }); setMsg('Zmieniono'); load() } catch(e:any){ setMsg(e.message) }
  }
  async function setTemp(id:number) {
    const t = prompt('Nowa temperatura docelowa:')
    if (!t) return
    try { await apiPost(`/api/sprzet/${id}/temperatura`, { temperatura:+t }); setMsg('Ustawiono') } catch(e:any){ setMsg(e.message) }
  }

  return (
    <div className="space-y-6">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}

      <section>
        <h2 className="font-bold text-lg mb-2">Sprzęt</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {sprzet.map(s=>(
            <div key={s.id} className="bg-slate-800 rounded p-3">
              <div className="font-semibold">{s.nazwa_unikalna} <span className="text-xs text-slate-400">({s.typ_sprzetu})</span></div>
              <div className="text-xs">Stan: {s.stan_sprzetu}</div>
              {s.id_partii && <div className="text-xs">Partia: {s.unikalny_kod}</div>}
              <div className="mt-2 flex gap-2">
                <button className="px-2 py-1 bg-slate-700 rounded" onClick={()=>setTemp(s.id)}>Ustaw temperaturę</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-bold text-lg mb-2">Zawory</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {zawory.map(z=>(
            <div key={z.id} className="bg-slate-800 rounded p-3 flex items-center justify-between">
              <div><div className="font-semibold">{z.nazwa_zaworu}</div><div className="text-xs">Stan: {z.stan}</div></div>
              <div className="flex gap-2">
                <button className="px-2 py-1 bg-green-700 rounded" onClick={()=>zmienStan(z.id, 'OTWARTY')}>Otwórz</button>
                <button className="px-2 py-1 bg-red-700 rounded" onClick={()=>zmienStan(z.id, 'ZAMKNIETY')}>Zamknij</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

