import { httpUrl } from '../backend'
export { inputDate, localDate, notionLink } from './state'

export type RecordRow = { id: string; title: string; kind: string; status: string; date: { start: string; end?: string | null } | null;
  url: string; last_edited_time: string; in_trash: boolean }
export type Connection = { connected: boolean; workflow_ready: boolean; missing_properties: string[]; name: string; database_url: string }
export type Pending = { id: string; summary: string; expires_ts: string }
export type Detail = { page: RecordRow; blocks: { id: string; type: string; text: string; checked?: boolean; has_children: boolean }[];
  truncated: boolean; preview_note: string }

export async function notionRequest<T>(token: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(httpUrl('/api/notion' + path), { method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(response.status === 401 ? 'Enter your Koe access token to connect.' :
    typeof data?.detail === 'string' ? [data.detail, data.hint].filter(Boolean).join(' ') : 'The request could not complete. Refresh and check the connection.')
  return data as T
}

