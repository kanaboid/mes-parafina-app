import { useEffect, useState } from 'react'
import { apiGet } from '../api'

export default function Filters() {
  const [basic, setBasic] = useState<any[]>([])
  const [details, setDetails] = useState<any[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try {
      setBasic(await apiGet('/api/filtry/status'))
      setDetails(await apiGet('/api/filtry/szczegolowy-status'))
    } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  return (
    <div className="space-y-6">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}
      <section>
        <h2 className="font-bold mb-2">Filtry - status</h2>
        <pre className="bg-slate-800 rounded p-3 overflow-auto text-xs">{JSON.stringify(basic, null, 2)}</pre>
      </section>
      <section>
        <h2 className="font-bold mb-2">Filtry - szczegóły</h2>
        <pre className="bg-slate-800 rounded p-3 overflow-auto text-xs">{JSON.stringify(details, null, 2)}</pre>
      </section>
    </div>
  )
}

