import { useEffect, useState } from 'react'
import { apiGet } from '../api'

export default function Home() {
  const [ops, setOps] = useState<any[]>([])
  const [sprzet, setSprzet] = useState<any[]>([])
  const [zawory, setZawory] = useState<any[]>([])
  const [alArmy, setAlArmy] = useState<any[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try {
      const [o, s, z, a] = await Promise.all([
        apiGet('/api/operations/aktywne').catch(()=>[]),
        apiGet('/api/sprzet').catch(()=>[]),
        apiGet('/api/zawory').catch(()=>[]),
        apiGet('/api/alarmy/aktywne').catch(()=>[])
      ])
      setOps(Array.isArray(o) ? o : []); 
      setSprzet(Array.isArray(s) ? s : []); 
      setZawory(Array.isArray(z) ? z : []); 
      setAlArmy(Array.isArray(a) ? a : [])
    } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  return (
    <div className="space-y-8">
      {msg && <div className="bg-yellow-900/30 border border-yellow-700 px-3 py-2 rounded">{msg}</div>}

      {/* Aktywne operacje */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-activity"/> Aktywne operacje</span>}>
        {ops.length === 0 ? (
          <div className="text-slate-400 text-sm">Brak aktywnych operacji</div>
        ) : (
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="text-slate-300">
                <tr className="border-b border-slate-700">
                  <th className="text-left py-2 pr-4">ID</th>
                  <th className="text-left py-2 pr-4">Typ</th>
                  <th className="text-left py-2 pr-4">ID Partii</th>
                  <th className="text-left py-2 pr-4">Start</th>
                  <th className="text-left py-2 pr-4">Opis</th>
                </tr>
              </thead>
              <tbody>
                {ops.map((o:any)=> (
                  <tr key={o.id} className="border-b border-slate-800">
                    <td className="py-2 pr-4">{o.id}</td>
                    <td className="py-2 pr-4">{o.typ_operacji}</td>
                    <td className="py-2 pr-4">{o.id_partii_surowca ?? '-'}</td>
                    <td className="py-2 pr-4">{o.czas_rozpoczecia ?? '-'}</td>
                    <td className="py-2 pr-4">{o.opis ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Alarmy */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-exclamation-triangle"/> Alarmy</span>}>
        {alArmy.length === 0 ? (
          <div className="text-slate-400 text-sm">Brak aktywnych alarmów</div>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {alArmy.map((a:any)=> (
              <div key={a.id} className="bg-red-900/20 border border-red-700 rounded p-3">
                <div className="font-semibold">{a.nazwa_sprzetu}</div>
                <div className="text-xs">{a.typ_alarmu}</div>
                <div className="text-xs">{a.czas_wystapienia}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Stan sprzętu */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-diagram-3"/> Aktualny stan sprzętu</span>}>
        <div className="grid md:grid-cols-2 gap-3">
          {sprzet.map((s:any)=> (
            <div key={s.id} className="bg-slate-800 rounded p-3 border border-slate-700">
              <div className="font-semibold">{s.nazwa_unikalna} <span className="text-xs text-slate-400">({s.typ_sprzetu})</span></div>
              <div className="text-xs">Stan: {s.stan_sprzetu}</div>
              {s.unikalny_kod && <div className="text-xs">Partia: {s.unikalny_kod}</div>}
            </div>
          ))}
        </div>
      </Card>

      {/* Zawory */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-toggles"/> Stan zaworów</span>}>
        <div className="grid md:grid-cols-2 gap-3">
          {zawory.map((z:any)=> (
            <div key={z.id} className="bg-slate-800 rounded p-3 border border-slate-700 flex items-center justify-between">
              <div>
                <div className="font-semibold">{z.nazwa_zaworu}</div>
                <div className="text-xs">{z.stan}</div>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${z.stan==='OTWARTY'?'bg-green-900/30 border border-green-700':'bg-slate-900/30 border border-slate-700'}`}>{z.stan}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function Card({ title, children }: any){
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800">
      <div className="px-4 py-3 border-b border-slate-700 font-semibold flex items-center gap-2">{title}</div>
      <div className="p-4">{children}</div>
    </div>
  )
}

