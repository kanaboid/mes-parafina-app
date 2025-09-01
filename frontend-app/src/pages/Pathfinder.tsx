import { useState } from 'react'
import { apiPost } from '../api'

export default function Pathfinder() {
  const [result, setResult] = useState<any>(null)
  const [msg, setMsg] = useState<string | null>(null)

  async function test(form:any) {
    try {
      const data = await apiPost('/topology/api/pathfinder/test-connection', {
        start_point: form.start_point, end_point: form.end_point, valve_states: form.valve_states ? form.valve_states.split(',').map((s:string)=>s.trim()) : undefined
      })
      setResult(data); setMsg(null)
    } catch(e:any){ setMsg(e.message) }
  }

  async function find(form:any) {
    try {
      const data = await apiPost('/topology/api/pathfinder/find-paths', {
        start_point: form.start_point, end_point: form.end_point, max_paths: form.max_paths ? +form.max_paths : 5
      })
      setResult(data); setMsg(null)
    } catch(e:any){ setMsg(e.message) }
  }

  return (
    <div className="space-y-4">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}

      <Form title="Test połączenia" onSubmit={test}>
        <Input name="start_point" label="Start (np. R1_OUT)" />
        <Input name="end_point" label="Koniec (np. R2_IN)" />
        <Input name="valve_states" label="Stany zaworów (CSV nazwy, opc.)" />
      </Form>

      <Form title="Znajdź ścieżki" onSubmit={find}>
        <Input name="start_point" label="Start" />
        <Input name="end_point" label="Koniec" />
        <Input name="max_paths" label="Max ścieżek (domyślnie 5)" />
      </Form>

      <section>
        <h3 className="font-bold">Wynik</h3>
        <pre className="bg-slate-800 rounded p-3 overflow-auto text-xs">{JSON.stringify(result, null, 2)}</pre>
      </section>
    </div>
  )
}

function Form({ title, children, onSubmit }: any){
  const [state, set] = useState<any>({})
  return (
    <div className="bg-slate-800 rounded p-3">
      <h3 className="font-semibold mb-2">{title}</h3>
      <form className="grid md:grid-cols-3 gap-2" onSubmit={e=>{e.preventDefault(); onSubmit(state)}}>
        {Array.isArray(children)? children.map((c:any)=>({...c, props:{...c.props, onChange:(e:any)=>set((s:any)=>({...s,[e.target.name]:e.target.value})), value:state[c.props.name] ?? ''}})) : children}
        <div className="md:col-span-3">
          <button className="px-3 py-1 bg-cyan-700 rounded">Wyślij</button>
        </div>
      </form>
    </div>
  )
}
function Input({ label, name, type='text', ...rest }: any){
  return (
    <label className="text-sm grid gap-1">
      <span className="text-slate-300">{label}</span>
      <input name={name} type={type} className="px-2 py-1 rounded bg-slate-900 border border-slate-700" {...rest}/>
    </label>
  )
}

