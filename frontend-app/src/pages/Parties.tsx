import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'

export default function Parties() {
  const [list, setList] = useState<any[]>([])
  const [sel, setSel] = useState<any | null>(null)
  const [cycles, setCycles] = useState<any[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try { setList(await apiGet('/api/partie/aktywne')) } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  async function pick(id:number) {
    try {
      setSel(await apiGet(`/api/partie/szczegoly/${id}`))
      setCycles(await apiGet(`/api/cykle-filtracyjne/${id}`))
    } catch(e:any){ setMsg(e.message) }
  }

  async function updateStatus(id:number) {
    const nowy_status = prompt('Nowy status:')
    if (!nowy_status) return
    try { await apiPost('/api/partie/aktualizuj-status', { id_partii:id, nowy_status }); setMsg('Zmieniono'); pick(id) } catch(e:any){ setMsg(e.message) }
  }

  async function startCycle(id:number) {
    const typ = prompt('typ_cyklu: placek | filtracja | dmuchanie') || 'placek'
    const id_filtra = prompt('ID filtra (liczba lub nazwa)') || ''
    const reaktor_startowy = prompt('Reaktor startowy (nazwa)') || ''
    try { await apiPost('/api/cykle/rozpocznij', { id_partii:id, typ_cyklu:typ, id_filtra, reaktor_startowy }); setMsg('Cykl rozpoczęty'); pick(id) } catch(e:any){ setMsg(e.message) }
  }
  async function endCycle(id:number) {
    try { await apiPost('/api/cykle/zakoncz', { id_partii:id }); setMsg('Cykl zakończony'); pick(id) } catch(e:any){ setMsg(e.message) }
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-bold text-lg">Aktywne partie</h2>
          <button className="px-3 py-1 bg-cyan-700 rounded" onClick={load}>Odśwież</button>
        </div>
        <div className="space-y-2">
          {list.map(p=> (
            <div key={p.id} className="bg-slate-800 rounded p-3 cursor-pointer" onClick={()=>pick(p.id)}>
              <div className="font-semibold">{p.unikalny_kod} — {p.nazwa_partii}</div>
              <div className="text-xs">{p.nazwa_sprzetu} — {p.status_partii}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        {msg && <div className="bg-slate-700 px-3 py-2 rounded mb-2">{msg}</div>}
        {sel ? (
          <div className="space-y-3">
            <div className="bg-slate-800 rounded p-3">
              <div className="font-bold">{sel.unikalny_kod}</div>
              <div className="text-xs">{sel.nazwa_sprzetu} — {sel.status_partii}</div>
              <div className="mt-2 flex gap-2">
                <button className="px-3 py-1 bg-slate-700 rounded" onClick={()=>updateStatus(sel.id)}>Zmień status</button>
                <button className="px-3 py-1 bg-green-700 rounded" onClick={()=>startCycle(sel.id)}>Start cyklu</button>
                <button className="px-3 py-1 bg-red-700 rounded" onClick={()=>endCycle(sel.id)}>Zakończ cykl</button>
              </div>
            </div>
            <div className="bg-slate-800 rounded p-3">
              <div className="font-semibold mb-2">Szczegóły</div>
              <pre className="text-xs overflow-auto">{JSON.stringify(sel, null, 2)}</pre>
            </div>
            <div className="bg-slate-800 rounded p-3">
              <div className="font-semibold mb-2">Cykle</div>
              <pre className="text-xs overflow-auto">{JSON.stringify(cycles, null, 2)}</pre>
            </div>
          </div>
        ) : <div className="text-slate-400">Wybierz partię...</div>}
      </div>
    </div>
  )
}

