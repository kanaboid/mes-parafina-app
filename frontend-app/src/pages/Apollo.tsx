import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'

export default function Apollo() {
  const [lista, setLista] = useState<any[]>([])
  const [stan, setStan] = useState<any|null>(null)
  const [hist, setHist] = useState<any[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  async function load() {
    try { setLista(await apiGet('/api/apollo/lista-stanow')) } catch(e:any){ setMsg(e.message) }
  }
  useEffect(()=>{ load() }, [])

  async function getStan(id:number) {
    try { setStan(await apiGet(`/api/apollo/stan/${id}`)) } catch(e:any){ setMsg(e.message) }
  }
  async function getHistoriaSesji(id:number) {
    try { setHist(await apiGet(`/api/apollo/sesja/${id}/historia`)) } catch(e:any){ setMsg(e.message) }
  }

  async function call(ep:string, payload:any, ok='OK'){ try { await apiPost(ep, payload); setMsg(ok); load() } catch(e:any){ setMsg(e.message) } }

  return (
    <div className="space-y-6">
      {msg && <div className="bg-slate-700 px-3 py-2 rounded">{msg}</div>}

      <section>
        <h2 className="font-bold mb-2">Stany Apollo</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {lista.map(a=> (
            <div key={a.id_sprzetu || a.id} className="bg-slate-800 rounded p-3">
              <div className="font-semibold">{a.nazwa_apollo || a.nazwa_unikalna}</div>
              <div className="text-xs">Dostępne: {a.dostepne_kg} kg</div>
              <div className="text-xs">Typ: {a.typ_surowca}</div>
              <div className="mt-2 flex gap-2">
                <button className="px-2 py-1 bg-slate-700 rounded" onClick={()=>getStan(a.id_sprzetu || a.id)}>Szczegóły</button>
              </div>
            </div>
          ))}
        </div>
        {stan && <pre className="bg-slate-800 rounded p-3 text-xs overflow-auto mt-3">{JSON.stringify(stan, null, 2)}</pre>}
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        <Card title="Rozpocznij sesję">
          <Form onSubmit={(d:any)=>call('/api/apollo/rozpocznij-sesje', { id_sprzetu:+d.id_sprzetu, typ_surowca:d.typ_surowca, waga_kg:+d.waga_kg }, 'Sesja rozpoczęta')}>
            <Input name="id_sprzetu" label="ID Apollo" />
            <Input name="typ_surowca" label="Typ surowca" />
            <Input name="waga_kg" label="Waga początkowa (kg)" />
          </Form>
        </Card>

        <Card title="Dodaj surowiec">
          <Form onSubmit={(d:any)=>call('/api/apollo/dodaj-surowiec', { id_sprzetu:+d.id_sprzetu, waga_kg:+d.waga_kg }, 'Dodano')}>
            <Input name="id_sprzetu" label="ID Apollo" />
            <Input name="waga_kg" label="Waga (kg)" />
          </Form>
        </Card>

        <Card title="Korekta stanu">
          <Form onSubmit={(d:any)=>call('/api/apollo/koryguj-stan', { id_sprzetu:+d.id_sprzetu, rzeczywista_waga_kg:+d.rzeczywista_waga_kg, uwagi:d.uwagi }, 'Skorygowano')}>
            <Input name="id_sprzetu" label="ID Apollo" />
            <Input name="rzeczywista_waga_kg" label="Rzeczywista waga (kg)" />
            <Input name="uwagi" label="Uwagi" />
          </Form>
        </Card>

        <Card title="Zakończ sesję">
          <Form onSubmit={(d:any)=>call('/api/apollo/zakoncz-sesje', { id_sprzetu:+d.id_sprzetu }, 'Zakończono')}>
            <Input name="id_sprzetu" label="ID Apollo" />
          </Form>
        </Card>
      </section>

      <section>
        <h3 className="font-bold mb-2">Historia sesji (po ID sesji)</h3>
        <Form onSubmit={(d:any)=>getHistoriaSesji(+d.id_sesji)}>
          <Input name="id_sesji" label="ID sesji" />
        </Form>
        <pre className="bg-slate-800 rounded p-3 text-xs overflow-auto mt-3">{JSON.stringify(hist, null, 2)}</pre>
      </section>
    </div>
  )
}

function Card({ title, children }: any){
  return <div className="bg-slate-800 rounded p-3"><div className="font-semibold mb-2">{title}</div>{children}</div>
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

