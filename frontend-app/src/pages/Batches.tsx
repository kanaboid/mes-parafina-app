import { useState } from 'react'
import { apiGet, apiPost } from '../api'

export default function Batches() {
  const [tankStatus, setTankStatus] = useState<any|null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  async function call(ep:string, payload:any, ok='OK'){ try { await apiPost(ep, payload); setMsg(ok) } catch(e:any){ setMsg(e.message) } }
  async function getTank(id:number){ try { setTankStatus(await apiGet(`/api/batches/tanks/${id}/status`)) } catch(e:any){ setMsg(e.message) } }

  return (
    <div className="space-y-6">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}

      <div className="grid md:grid-cols-2 gap-4">
        <Card title="Receive from tanker">
          <Form onSubmit={(d:any)=>call('/api/batches/receive/from-tanker', { material_type:d.material_type, source_name:d.source_name, quantity_kg:+d.quantity_kg }, 'Zarejestrowano')}>
            <Input name="material_type" label="Material type" />
            <Input name="source_name" label="Source name" />
            <Input name="quantity_kg" label="Quantity (kg)" />
          </Form>
        </Card>

        <Card title="Receive from Apollo">
          <Form onSubmit={(d:any)=>call('/api/batches/receive/from-apollo', { material_type:d.material_type, source_name:d.source_name, quantity_kg:+d.quantity_kg }, 'Zarejestrowano')}>
            <Input name="material_type" label="Material type" />
            <Input name="source_name" label="Source name" />
            <Input name="quantity_kg" label="Quantity (kg)" />
          </Form>
        </Card>

        <Card title="Transfer to dirty tank">
          <Form onSubmit={(d:any)=>call('/api/batches/transfer/to-dirty-tank', { batch_id:+d.batch_id, tank_id:+d.tank_id }, 'Przelano')}>
            <Input name="batch_id" label="Batch ID" />
            <Input name="tank_id" label="Tank ID" />
          </Form>
        </Card>

        <Card title="Transfer tank → tank">
          <Form onSubmit={(d:any)=>call('/api/batches/transfer/tank-to-tank', { source_tank_id:+d.source_tank_id, destination_tank_id:+d.destination_tank_id, quantity_kg:+d.quantity_kg }, 'Przelano')}>
            <Input name="source_tank_id" label="Source tank ID" />
            <Input name="destination_tank_id" label="Destination tank ID" />
            <Input name="quantity_kg" label="Quantity (kg)" />
          </Form>
        </Card>
      </div>

      <Card title="Tank status">
        <Form onSubmit={(d:any)=>getTank(+d.tank_id)}>
          <Input name="tank_id" label="Tank ID" />
        </Form>
        <pre className="bg-slate-800 rounded p-3 text-xs overflow-auto mt-3">{JSON.stringify(tankStatus, null, 2)}</pre>
      </Card>
    </div>
  )
}

function Card({ title, children }: any){
  return (
    <div className="bg-slate-800 rounded p-3">
      <div className="font-semibold mb-2">{title}</div>
      {children}
    </div>
  )
}
function Form({ children, onSubmit, initial }: any) {
  const [state, setState] = useState<any>(initial || {})
  function handle(e:any){ setState((s:any)=>({ ...s, [e.target.name]: e.target.value })) }
  return (
    <form className="grid gap-2" onSubmit={e=>{e.preventDefault(); onSubmit(state)}}>
      {Array.isArray(children)? children.map((c:any)=>({...c, props:{...c.props, onChange:handle, value:state[c.props.name] ?? ''}})) : children}
      <button className="px-3 py-1 bg-cyan-700 rounded">Wyślij</button>
    </form>
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

