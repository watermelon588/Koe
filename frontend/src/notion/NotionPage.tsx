import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowSquareOut, ArrowsClockwise, Check, Columns, FileText, MagnifyingGlass, Plus, Trash, X } from '@phosphor-icons/react'
import { inputDate, localDate, notionLink, notionRequest, type Connection, type Detail, type Pending, type RecordRow } from './api'
import { AddPropertyForm, PropertyFields, type FieldValues, type Schema } from './NotionFields'
import './notion.css'

type Draft = { title: string; kind: string; status: string; date: string; end: string; body: string; page_id: string; expected_edited: string }
const blank = (): Draft => ({ title: '', kind: 'Note', status: 'Open', date: localDate(), end: '', body: '', page_id: '', expected_edited: '' })
type Result = { error?: { message: string; hint?: string }; status?: string; title?: string; url?: string; message?: string; added_properties?: string[] }

export function NotionPage({ token, onToken }: { token: string; onToken: (value: string) => void }) {
  const [connection, setConnection] = useState<Connection | null>(null)
  const [rows, setRows] = useState<RecordRow[]>([])
  const [detail, setDetail] = useState<Detail | null>(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('')
  const [cursor, setCursor] = useState<string | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [fields, setFields] = useState<FieldValues>({})
  const [schema, setSchema] = useState<Schema | null>(null)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refreshed, setRefreshed] = useState('')
  const [activity, setActivity] = useState<{ id: string; ts: string; summary: string; tool?: string; kind: string }[]>([])
  const [activityUnavailable, setActivityUnavailable] = useState(false)
  const [clock, setClock] = useState(Date.now)
  const [tokenDraft, setTokenDraft] = useState(token)
  const generation = useRef(0)
  const invalidate = useCallback(() => { generation.current++ }, [])
  const request = useCallback(<T,>(path: string, body?: unknown) => notionRequest<T>(token, path, body), [token])
  const editor = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    if (!token) return
    const gen = ++generation.current
    setBusy('Loading workspace'); setError('')
    try {
      const status = await request<Connection>('/status')
      if (gen !== generation.current) return
      setConnection(status)
      const [list, approval, audit, properties] = await Promise.all([
        request<{ pages: RecordRow[]; next_cursor: string | null }>('/records?' + new URLSearchParams({ query, kind })),
        request<{ pending_action: Pending | null }>('/pending'),
        request<{ activity: typeof activity; unavailable?: boolean }>('/activity').catch(() => ({ activity: [], unavailable: true })),
        status.workflow_ready ? request<Schema>('/schema').catch(() => null) : Promise.resolve(null), // read before offering optional fields
      ])
      if (gen !== generation.current) return
      setRows(list.pages); setCursor(list.next_cursor); setPending(approval.pending_action)
      setActivity(audit.activity)
      setSchema(properties)
      setActivityUnavailable(!!audit.unavailable)
      setRefreshed(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    } catch (e) { if (gen === generation.current) setError(e instanceof Error ? e.message : 'Could not load Notion.') }
    finally { if (gen === generation.current) setBusy('') }
  }, [token, request, query, kind])

  useEffect(() => { const timer = setTimeout(() => void refresh(), 350); return () => { clearTimeout(timer); invalidate() } }, [refresh, invalidate])
  const editing = !!draft
  const editedPage = draft?.page_id
  useEffect(() => { if (editing) editor.current?.focus() }, [editedPage, editing])
  useEffect(() => { if (!pending) return; const id = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(id) }, [pending])
  const expired = pending && new Date(pending.expires_ts).getTime() <= clock

  async function run(label: string, operation: () => Promise<void>) {
    if (busy) return
    setBusy(label); setError(''); setNotice('')
    try { await operation() }
    catch (e) { setError(e instanceof Error ? e.message : 'The operation did not complete. Check Notion before retrying.') }
    finally { setBusy('') }
  }

  function inspectResult(result: Result) {
    if (result.error) throw new Error([result.error.message, result.error.hint].filter(Boolean).join(' '))
  }

  async function open(row: RecordRow) {
    const gen = ++generation.current
    setBusy('Reading record'); setError(''); setDraft(null)
    try { const data = await request<Detail>('/records/' + row.id); if (gen === generation.current) setDetail(data) }
    catch (e) { if (gen === generation.current) setError(e instanceof Error ? e.message : 'Could not read this record.') }
    finally { if (gen === generation.current) setBusy('') }
  }

  async function propose(tool: string, args: unknown) {
    const data = await request<Result & { pending_action?: Pending }>('/proposals', { tool, args })
    inspectResult(data)
    if (data.pending_action) { setPending(data.pending_action); setDraft(null); setAdding(false); setFields({}); setNotice('Review the complete change below. Nothing has been saved yet.') }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!draft) return
    void run('Preparing preview', async () => {
      const args = { ...draft, date: draft.kind === 'Meeting' ? new Date(draft.date).toISOString() : draft.date,
        end: draft.kind === 'Meeting' ? new Date(draft.end).toISOString() : '',
        ...(Object.keys(fields).length ? { fields } : {}) } // only the properties the person touched
      await propose('notion_save', args)
    })
  }

  function edit(row: RecordRow) {
    setFields({}); setAdding(false)
    setDraft({ title: row.title, kind: row.kind, status: row.status, date: inputDate(row.date?.start ?? localDate(), row.kind === 'Meeting'),
      end: row.date?.end ? inputDate(row.date.end, true) : '', body: '', page_id: row.id, expected_edited: row.last_edited_time })
  }

  function decision(approve: boolean) {
    if (!pending) return
    void run(approve ? 'Saving to Notion' : 'Cancelling', async () => {
      const data = await request<{ result: Result; pending_action: Pending | null }>('/approvals/' + pending.id, { approve })
      setPending(data.pending_action); inspectResult(data.result)
      setNotice(data.result.status !== 'executed' ? 'Cancelled. Nothing changed.'
        : data.result.added_properties?.length ? `Added ${data.result.added_properties.join(', ')}. Fill it on a record as a separate change (New record or Edit record → More properties).`
        : data.result.message || 'Saved to Notion.')
      setDetail(null); await refresh()
    })
  }

  const update = (field: keyof Draft, value: string) => setDraft(d => d ? { ...d, [field]: value } : d)
  return <main className="notion-workspace" id="main-content" tabIndex={-1}>
    <div className="workspace-heading">
      <div><h1>Notion</h1><p>Your daily work, notes and next steps.</p></div>
      <div className="workspace-actions">
        <button className="ghost" onClick={() => void refresh()} disabled={!!busy || !token}><ArrowsClockwise />Refresh</button>
        <button className="ghost" disabled={!!busy || !connection?.workflow_ready || !!pending} onClick={() => { setAdding(true); setDraft(null); setDetail(null) }}><Columns />Add property</button>
        <button className="primary" disabled={!!busy || !connection?.workflow_ready || !!pending} onClick={() => { setDraft(blank()); setFields({}); setAdding(false); setDetail(null) }}><Plus />New record</button>
      </div>
    </div>
    {!token && <form className="workspace-connect" onSubmit={e => { e.preventDefault(); onToken(tokenDraft.trim()) }}>
      <label>Connect this device<input type="password" value={tokenDraft} onChange={e => setTokenDraft(e.target.value)} placeholder="Koe access token" autoComplete="off" /></label>
      <button className="soft" disabled={!tokenDraft.trim()}>Connect</button>
      <p>The database connection stays private on your backend.</p>
    </form>}
    <div className="workspace-connection" role="status">
      <span className="live-dot" data-on={!!connection?.connected && !error} aria-hidden="true" />
      <span>{error ? 'Connection needs attention' : connection ? `${connection.name} · ${connection.workflow_ready ? 'Ready' : 'Setup needed'}` : token ? 'Checking connection' : 'Not connected'}</span>
      {refreshed && <small>Refreshed {refreshed}</small>}
      {connection?.database_url && notionLink(connection.database_url) && <a href={notionLink(connection.database_url)} target="_blank" rel="noreferrer">Open database <ArrowSquareOut size={14} /></a>}
    </div>
    {error && <div className="workspace-feedback" role="alert"><p>{error}</p><button className="ghost" onClick={() => void refresh()} disabled={!!busy}>Check again</button></div>}
    {notice && <p className="workspace-notice" role="status">{notice}</p>}
    {connection && !connection.workflow_ready && <section className="workspace-setup">
      <h2>Prepare your database</h2><p>Koe needs these additional properties: {connection.missing_properties.join(', ')}. Adding them keeps existing records and properties.</p>
      <button className="soft" disabled={!!busy} onClick={() => void run('Preparing database', async () => {
        await request('/setup', { confirm: true }); await refresh(); setNotice('Database prepared. You can create records now.')
      })}>Add missing properties</button>
    </section>}
    {pending && <section className="workspace-approval" aria-label="Confirm Notion change">
      <div><h2>{expired ? 'This preview expired' : 'Review before saving'}</h2>
        <p className="approval-summary">{pending.summary}</p>{/* verbatim: the authoritative preview of the exact change */}
        <small>{expired ? 'Refresh to prepare a new change.' : `Destination: ${connection?.name || 'your configured Notion database'} · expires in ${countdown(pending.expires_ts, clock)}`}</small></div>
      <div className="pair"><button className="ghost" disabled={!!busy || !!expired} onClick={() => decision(false)}><X />Cancel</button>
        <button className="primary" disabled={!!busy || !!expired} onClick={() => decision(true)}><Check />Confirm change</button></div>
    </section>}
    <div className="workspace-layout" aria-busy={!!busy}>
      <section className="workspace-list" aria-label="Notion records">
        <form className="workspace-filter" onSubmit={e => { e.preventDefault(); void refresh() }}>
          <label className="workspace-search"><MagnifyingGlass /><input aria-label="Search record titles" placeholder="Search titles" value={query} maxLength={200} onChange={e => setQuery(e.target.value)} /></label>
          <select aria-label="Filter record type" value={kind} onChange={e => setKind(e.target.value)} disabled={!connection?.workflow_ready}>
            <option value="">All records</option>{['Daily log', 'Task', 'Meeting', 'Note'].map(k => <option key={k}>{k}</option>)}
          </select>
        </form>
        <div className="workspace-list-meta"><span>{busy || `${rows.length} records${cursor ? ' · more available' : ''}`}</span><span>Recently edited</span></div>
        {!rows.length && !busy && <div className="workspace-empty"><FileText size={28} /><h2>{query || kind ? 'No matching records' : 'A place for your work'}</h2>
          <p>{query || kind ? 'Try another title or record type.' : 'Create a note, task or meeting record. Ask Koe to log shipped work to start a daily log.'}</p></div>}
        <ul>{rows.map(row => <li key={row.id}><button className="record-row" aria-pressed={detail?.page.id === row.id} disabled={!!busy} onClick={() => void open(row)}>
          <span className="record-kind">{row.kind}</span><span className="record-title">{row.title}</span>
          <span className="record-meta">{row.date?.start.slice(0, 10) || 'No date'} <span>{row.status}</span></span>
        </button></li>)}</ul>
        {cursor && <button className="ghost workspace-more" disabled={!!busy} onClick={() => void run('Loading more records', async () => {
          const data = await request<{ pages: RecordRow[]; next_cursor: string | null }>('/records?' + new URLSearchParams({ query, kind, cursor }))
          setRows(old => [...old, ...data.pages.filter(p => !old.some(r => r.id === p.id))]); setCursor(data.next_cursor)
        })}>Load more</button>}
      </section>
      <section className="workspace-preview" aria-label="Record preview">
        {adding ? <AddPropertyForm disabled={!!busy || !!pending} onClose={() => setAdding(false)}
          onPropose={property => void run('Preparing property preview', () => propose('notion_add_properties', { properties: [property] }))} />
        : draft ? <form className="record-editor" onSubmit={submit}>
          <div className="record-editor-heading"><h2>{draft.page_id ? 'Edit record' : 'New record'}</h2><button className="icon-btn" type="button" aria-label="Close editor" onClick={() => setDraft(null)}><X /></button></div>
          <label>Title<input ref={editor} required maxLength={200} value={draft.title} onChange={e => update('title', e.target.value)} /></label>
          <div className="editor-pair"><label>Type<select value={draft.kind} onChange={e => setDraft(d => d ? { ...d, kind: e.target.value, date: localDate(), end: '' } : d)}>
            {['Note', 'Task', 'Meeting'].map(k => <option key={k}>{k}</option>)}</select></label>
            <label>Status<select value={draft.status} onChange={e => update('status', e.target.value)}>{['Open', 'In progress', 'Done'].map(s => <option key={s}>{s}</option>)}</select></label></div>
          <label>{draft.kind === 'Meeting' ? 'Starts (your local time)' : 'Date'}<input required type={draft.kind === 'Meeting' ? 'datetime-local' : 'date'} value={draft.date} onChange={e => update('date', e.target.value)} /></label>
          {draft.kind === 'Meeting' && <><label>Ends (your local time)<input required type="datetime-local" value={draft.end} onChange={e => update('end', e.target.value)} /></label>
            <p className="record-help">This saves meeting notes. To reserve a slot or invite people, ask Koe to book it in Calendar.</p></>}
          <label>{draft.page_id ? 'Additional notes (appended)' : 'Notes'}<textarea rows={7} maxLength={6000} value={draft.body} onChange={e => update('body', e.target.value)} /></label>
          <PropertyFields schema={schema} values={fields} onChange={setFields} />
          <p className="record-help">Existing page content is preserved. You’ll review the exact change before it is saved.</p>
          <button className="primary" disabled={!!busy || !!pending}>Preview change</button>
        </form> : detail ? <article className="record-detail">
          <div className="record-detail-meta"><span>{detail.page.kind} · {detail.page.status}</span>{notionLink(detail.page.url) && <a href={notionLink(detail.page.url)} target="_blank" rel="noreferrer" aria-label="Open record in Notion"><ArrowSquareOut /></a>}</div>
          <h2>{detail.page.title}</h2><p className="record-date">{detail.page.date?.start}{detail.page.date?.end ? ` → ${detail.page.date.end}` : ''}</p>
          {detail.page.kind === 'Meeting' && <p className="record-help">Meeting record only. Check Calendar for the booked slot.</p>}
          <div className="record-blocks">{detail.blocks.length ? detail.blocks.map((block, i) => <p key={block.id || i}>
            {block.type === 'to_do' ? <input type="checkbox" checked={!!block.checked} readOnly aria-label="Notion checklist state" /> : null}
            {block.text || `[${block.type.replaceAll('_', ' ')}]`}{block.has_children && <small>Nested content available in Notion</small>}</p>) : <p>No notes yet.</p>}</div>
          <p className="record-help">{detail.truncated ? 'Preview limited to 500 blocks. ' : ''}{detail.preview_note}</p>
          <div className="workspace-actions">{detail.page.kind !== 'Daily log' && <button className="soft" disabled={!!busy || !!pending} onClick={() => edit(detail.page)}>Edit record</button>}
            <button className="ghost" disabled={!!busy || !!pending} onClick={() => void run('Preparing trash preview', async () => {
              await propose('notion_archive', { page_id: detail.page.id, title: detail.page.title, expected_edited: detail.page.last_edited_time })
            })}><Trash />Move to trash</button></div>
        </article> : <div className="workspace-empty preview-empty"><FileText size={32} /><h2>See the whole picture</h2><p>Select a record to read its notes and properties, or create something new.</p>
          <p>Ask Koe: “Create a task to review my pull requests tomorrow.”</p></div>}
      </section>
    </div>
    <section className="workspace-history" aria-label="Recent Notion activity">
      <h2>Recent activity</h2>
      {activityUnavailable ? <p role="status">Activity could not be loaded. Your records and approval controls are still available.</p> : activity.length ? <ol>{activity.map(item => <li key={item.id}>
        <time dateTime={item.ts}>{new Date(item.ts).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time>
        <span>{item.tool ? `${item.tool.replace('notion_', '')} · ${item.summary}` : item.summary.replace('notion_', '').replaceAll('_', ' ')}</span>
      </li>)}</ol> : <p>Notion tool activity and approval outcomes appear here after you use Koe. Refresh to see the latest.</p>}
    </section>
  </main>
}

function countdown(expires: string, now: number) {
  const left = Math.max(0, Math.round((new Date(expires).getTime() - now) / 1000))
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`
}
