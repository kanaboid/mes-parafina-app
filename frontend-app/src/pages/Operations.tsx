import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost } from '../api'

type ActiveOp = { id:number; typ_operacji:string; opis?:string; czas_rozpoczecia?:string }

export default function Operations() {
  const [ops, setOps] = useState<ActiveOp[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  // Listy do selectów (inspirowane operacje.html)
  const [reaktoryPuste, setReaktoryPuste] = useState<any[]>([])
  const [reaktoryZSurowcem, setReaktoryZSurowcem] = useState<any[]>([])
  const [beczkiBrudne, setBeczkiBrudne] = useState<any[]>([])
  const [typySurowca, setTypySurowca] = useState<any[]>([])

  const loadOps = useCallback(async () => {
    try { setOps(await apiGet('/api/operations/aktywne')) } catch (e:any) { setMsg(e.message) }
  }, [])

  async function loadLists() {
    try {
      const [puste, zSurowcem, beczki, typy] = await Promise.all([
        apiGet('/api/sprzet/reaktory-puste'),
        apiGet('/api/sprzet/reaktory-z-surowcem'),
        apiGet('/api/sprzet/beczki-brudne'),
        apiGet('/api/typy-surowca')
      ])
      setReaktoryPuste(puste)
      setReaktoryZSurowcem(zSurowcem)
      setBeczkiBrudne(beczki)
      setTypySurowca(typy)
    } catch(e:any){ setMsg(e.message) }
  }

  useEffect(() => { loadOps(); const t=setInterval(loadOps, 8000); return ()=>clearInterval(t) }, [loadOps])
  useEffect(() => { loadLists() }, [])

  const cysternaOps = useMemo(()=>ops.filter(o=>o.typ_operacji==='ROZTANKOWANIE_CYSTERNY'),[ops])

  async function call(ep:string, body:any, ok='OK') {
    try { await apiPost(ep, body); setMsg(ok); loadOps() } catch(e:any){ setMsg(e.message) }
  }

  return (
    <div className="space-y-8">
      {msg && <div className="bg-yellow-900/30 border border-yellow-700 px-3 py-2 rounded">{msg}</div>}

      {/* Tankowanie Brudnego Surowca */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-droplet-fill"/> Tankowanie Brudnego Surowca</span>}>
        <Form onSubmit={(d:any)=> call('/api/operations/tankowanie-brudnego', {
          id_reaktora: +d.id_reaktora, id_beczki: +d.id_beczki, typ_surowca: d.typ_surowca, waga_kg: +d.waga_kg, temperatura_surowca: +d.temperatura_surowca
        }, 'Operacja rozpoczęta') }>
          <Select name="id_reaktora" label="Reaktor docelowy" placeholder="Wybierz reaktor (Pusty)" options={reaktoryPuste.map((r:any)=>({ value:r.id, label:r.nazwa_unikalna }))} />
          <Select name="id_beczki" label="Beczka źródłowa" placeholder="Wybierz beczkę (brudna)" options={beczkiBrudne.map((b:any)=>({ value:b.id, label:b.nazwa_unikalna }))} />
          <Select name="typ_surowca" label="Typ surowca" placeholder="Wybierz typ" options={typySurowca.map((t:any)=>({ value:t.nazwa, label:t.nazwa }))} />
          <Input name="waga_kg" label="Waga (kg)" type="number" />
          <Input name="temperatura_surowca" label="Temperatura początkowa (°C)" type="number" />
          <Submit>Zatwierdź</Submit>
        </Form>
      </Card>

      {/* Transfer Między Reaktorami */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-arrow-left-right"/> Transfer Między Reaktorami</span>}>
        <Form onSubmit={(d:any)=> call('/api/operations/transfer-reaktorow', {
          id_reaktora_zrodlowego: +d.id_reaktora_zrodlowego, id_reaktora_docelowego: +d.id_reaktora_docelowego, id_filtra: d.id_filtra || undefined
        }, 'Transfer uruchomiony') }>
          <Select name="id_reaktora_zrodlowego" label="Reaktor źródłowy" placeholder="Reaktory z surowcem" options={reaktoryZSurowcem.map((r:any)=>({ value:r.id, label:r.nazwa_unikalna }))} />
          <Select name="id_reaktora_docelowego" label="Reaktor docelowy" placeholder="Reaktory puste" options={reaktoryPuste.map((r:any)=>({ value:r.id, label:r.nazwa_unikalna }))} />
          <Input name="id_filtra" label="ID Filtra (opcjonalnie)" />
          <Submit>Rozpocznij</Submit>
        </Form>
      </Card>

      {/* Roztankowanie Cysterny */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-truck"/> Roztankowanie Cysterny</span>}>
        <div className="grid md:grid-cols-3 gap-4">
          <Form onSubmit={(d:any)=> call('/api/operations/roztankuj-cysterne/start', { id_cysterny:+d.id_cysterny, id_celu:+d.id_celu }, 'Start OK') }>
            <Input name="id_cysterny" label="ID Cysterny" />
            <Input name="id_celu" label="ID Celu" />
            <Submit>Start</Submit>
          </Form>
          <Form onSubmit={(d:any)=> call('/api/operations/roztankuj-cysterne/zakoncz', {
            id_operacji:+d.id_operacji, waga_netto_kg:+d.waga_netto_kg, typ_surowca:d.typ_surowca, nr_rejestracyjny:d.nr_rejestracyjny, nr_dokumentu_dostawy:d.nr_dokumentu_dostawy, nazwa_dostawcy:d.nazwa_dostawcy
          }, 'Zakończono') }>
            <Input name="id_operacji" label="ID Operacji" defaultValue={cysternaOps[0]?.id ?? ''} />
            <Input name="waga_netto_kg" label="Waga netto (kg)" type="number" />
            <Input name="typ_surowca" label="Typ surowca" />
            <Input name="nr_rejestracyjny" label="Nr rejestracyjny" />
            <Input name="nr_dokumentu_dostawy" label="Nr dokumentu dostawy" />
            <Input name="nazwa_dostawcy" label="Nazwa dostawcy" />
            <Submit>Zakończ</Submit>
          </Form>
          <Form onSubmit={(d:any)=> call('/api/operations/roztankuj-cysterne/anuluj', { id_operacji:+d.id_operacji }, 'Anulowano') }>
            <Input name="id_operacji" label="ID Operacji" defaultValue={cysternaOps[0]?.id ?? ''} />
            <Submit>Anuluj</Submit>
          </Form>
        </div>
      </Card>

      {/* Apollo */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-lightning"/> Apollo - transfer</span>}>
        <div className="grid md:grid-cols-3 gap-4">
          <Form onSubmit={(d:any)=> call('/api/operations/apollo-transfer/start', { id_zrodla:+d.id_zrodla, id_celu:+d.id_celu }, 'Start OK') }>
            <Input name="id_zrodla" label="ID Apollo" />
            <Input name="id_celu" label="ID Celu" />
            <Submit>Start</Submit>
          </Form>
          <Form onSubmit={(d:any)=> call('/api/operations/apollo-transfer/end', { id_operacji:+d.id_operacji, waga_kg:+d.waga_kg }, 'Zakończono') }>
            <Input name="id_operacji" label="ID Operacji" />
            <Input name="waga_kg" label="Waga (kg)" type="number" />
            <Submit>Zakończ</Submit>
          </Form>
          <Form onSubmit={(d:any)=> call('/api/operations/apollo-transfer/anuluj', { id_operacji:+d.id_operacji }, 'Anulowano') }>
            <Input name="id_operacji" label="ID Operacji" />
            <Submit>Anuluj</Submit>
          </Form>
        </div>
      </Card>

      {/* Aktywne operacje */}
      <Card title={<span className="flex items-center gap-2"><i className="bi bi-activity"/> Aktywne operacje</span>}>
        <div className="space-y-2">
          {ops.map(o => (
            <div key={o.id} className="bg-slate-900 px-3 py-2 rounded flex items-center justify-between">
              <div>
                <div className="font-semibold">{o.typ_operacji}</div>
                <div className="text-xs text-slate-400">{o.opis}</div>
              </div>
              <div className="flex gap-2">
                <button className="px-3 py-1 bg-cyan-700 rounded" onClick={()=>call('/api/operations/zakoncz', { id_operacji:o.id }, 'Zakończono')}>Zakończ</button>
                {o.typ_operacji.includes('APOLLO') && (
                  <>
                    <button className="px-3 py-1 bg-slate-700 rounded" onClick={()=>{
                      const w = prompt('Waga (kg):')
                      if (w) call('/api/operations/apollo-transfer/end', { id_operacji:o.id, waga_kg:+w }, 'Zakończono')
                    }}>Zakończ (Apollo)</button>
                    <button className="px-3 py-1 bg-red-700 rounded" onClick={()=>call('/api/operations/apollo-transfer/anuluj', { id_operacji:o.id }, 'Anulowano')}>Anuluj</button>
                  </>
                )}
              </div>
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

function Form({ children, onSubmit, initial }: any) {
  const [state, setState] = useState<any>(initial || {})
  function handle(e:any){ setState((s:any)=>({ ...s, [e.target.name]: e.target.value })) }
  return (
    <form className="grid md:grid-cols-2 gap-3" onSubmit={e=>{e.preventDefault(); onSubmit(state)}}>
      {Array.isArray(children)? children.map((c:any)=> c?.props?.name ? {...c, props:{...c.props, onChange:handle, value:state[c.props.name] ?? c.props.defaultValue ?? ''}} : c) : children}
    </form>
  )
}
function Input({ label, name, type='text', ...rest }: any) {
  return (
    <label className="text-sm grid gap-1">
      <span className="text-slate-300">{label}</span>
      <input name={name} type={type} className="px-2 py-2 rounded bg-slate-900 border border-slate-700" {...rest}/>
    </label>
  )
}
function Select({ label, name, options, placeholder, ...rest }: any){
  return (
    <label className="text-sm grid gap-1">
      <span className="text-slate-300">{label}</span>
      <select name={name} className="px-2 py-2 rounded bg-slate-900 border border-slate-700" {...rest}>
        <option value="">{placeholder || 'Wybierz...'}</option>
        {options?.map((o:any)=>(<option key={o.value} value={o.value}>{o.label}</option>))}
      </select>
    </label>
  )
}
function Submit({ children }: any){
  return <button className="mt-1 px-3 py-2 bg-cyan-700 rounded md:col-span-2">{children}</button>
}

