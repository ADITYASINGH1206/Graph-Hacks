import { API_BASE, ApiError } from './api'

export interface AskEvent {
  event: string
  // Payloads are checked where they are used; the contract is in docs/API_CONTRACT.md.
  data: Record<string, any>
}

/** Parse one SSE frame ("event: x\ndata: {...}") into an event, or null if it has no data. */
export function parseFrame(frame: string): AskEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const raw of frame.split(/\r?\n/)) {
    if (raw.startsWith('event:')) event = raw.slice(6).trim()
    else if (raw.startsWith('data:')) data.push(raw.slice(5).replace(/^ /, ''))
  }
  if (data.length === 0) return null
  try {
    return { event, data: JSON.parse(data.join('\n')) }
  } catch {
    return null
  }
}

/** Stream POST /ask as events. Throws ApiError if the request itself fails. */
export async function* streamAsk(
  question: string,
  signal: AbortSignal,
  sessionId?: string,
): AsyncGenerator<AskEvent> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionId }),
      signal,
    })
  } catch (err) {
    if (signal.aborted) throw err
    throw new ApiError(0, 'Cannot reach the backend. Is `dig serve` running?')
  }
  if (!res.ok || !res.body) {
    let detail = `The server answered HTTP ${res.status}.`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg) detail = String(body.detail[0].msg)
    } catch {
      // keep the generic message
    }
    throw new ApiError(res.status, detail)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const ev = parseFrame(frame)
      if (ev) yield ev
    }
  }
  const last = parseFrame(buffer)
  if (last) yield last
}
