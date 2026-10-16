export const API_BASE: string = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    const d = body?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg)
  } catch {
    // fall through
  }
  return `Request failed (HTTP ${res.status})`
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { signal })
  } catch (err) {
    if (signal?.aborted) throw err
    throw new ApiError(0, 'Cannot reach the backend. Is `dig serve` running?')
  }
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return (await res.json()) as T
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (signal?.aborted) throw err
    throw new ApiError(0, 'Cannot reach the backend. Is `dig serve` running?')
  }
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return (await res.json()) as T
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return 'n/a'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toISOString().slice(0, 10)
}
