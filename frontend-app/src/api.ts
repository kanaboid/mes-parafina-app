const API_BASE_URL = import.meta.env.PROD 
  ? 'https://mes-parafina-app-production.up.railway.app'  // URL Twojego Railway backend
  : ''

export async function apiGet<T = any>(url: string): Promise<T> {
  const fullUrl = `${API_BASE_URL}${url}`
  const res = await fetch(fullUrl)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data && (data.error || data.message)) || `HTTP ${res.status}`)
  return data
}

export async function apiPost<T = any>(url: string, payload: any): Promise<T> {
  const fullUrl = `${API_BASE_URL}${url}`
  const res = await fetch(fullUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data && (data.error || data.message)) || `HTTP ${res.status}`)
  return data
}

