export async function apiGet<T = any>(url: string): Promise<T> {
  const res = await fetch(url)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data && (data.error || data.message)) || `HTTP ${res.status}`)
  return data
}

export async function apiPost<T = any>(url: string, payload: any): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data && (data.error || data.message)) || `HTTP ${res.status}`)
  return data
}

