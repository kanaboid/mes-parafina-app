import { useState } from 'react'

export default function ApiExplorer() {
  const [url, setUrl] = useState('/api/sprzet')
  const [method, setMethod] = useState<'GET'|'POST'>('GET')
  const [body, setBody] = useState('{}')
  const [out, setOut] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)

  async function run() {
    try {
      const res = await fetch(url, {
        method,
        headers: method==='POST' ? { 'Content-Type': 'application/json' } : undefined,
        body: method==='POST' ? body : undefined
      })
      const data = await res.json().catch(()=> ({}))
      if (!res.ok) throw new Error(data?.message || data?.error || `HTTP ${res.status}`)
      setOut(data); setErr(null)
    } catch(e:any){ setErr(e.message) }
  }

  return (
    <div className="space-y-3">
      <div className="grid md:grid-cols-4 gap-2">
        <select className="bg-slate-800 rounded px-2" value={method} onChange={e=>setMethod(e.target.value as any)}>
          <option>GET</option>
          <option>POST</option>
        </select>
        <input className="bg-slate-800 rounded px-2 md:col-span-3" value={url} onChange={e=>setUrl(e.target.value)} />
      </div>
      {method==='POST' && <textarea className="w-full h-32 bg-slate-800 rounded p-2 font-mono text-xs" value={body} onChange={e=>setBody(e.target.value)} />}
      <button className="px-3 py-1 bg-cyan-700 rounded" onClick={run}>Wyślij</button>
      {err && <div className="bg-red-900/40 border border-red-700 rounded p-2 text-sm">{err}</div>}
      <pre className="bg-slate-800 rounded p-3 text-xs overflow-auto">{JSON.stringify(out, null, 2)}</pre>
    </div>
  )
}

