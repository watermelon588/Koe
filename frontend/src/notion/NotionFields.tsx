import { useState, type FormEvent } from 'react'
import { Plus, X } from '@phosphor-icons/react'

// Optional Notion properties (docs/FRONTEND_BACKEND_HANDOFF.md, "Notion workspace"). Controls come from the database's
// actual schema (GET /api/notion/schema): exact names and existing options only, never invented. A property the person
// didn't touch is left out of `fields`, so Notion keeps its value; clearing (null), an unticked checkbox (false) and an
// empty multi-select ([]) are explicit values that are sent.
export type SchemaField = { name: string; type: string; options: string[] }
export type Schema = { source_id: string; editable: SchemaField[]; read_only_or_reserved: string[]; partial: boolean; note: string }
export type FieldValues = Record<string, string | number | boolean | string[] | null>

const CLEARABLE = new Set(['rich_text', 'number', 'date', 'url', 'email', 'select', 'status'])
const MAX_FIELDS = 20 // backend limit per action

export function PropertyFields({ schema, values, onChange }: {
  schema: Schema | null; values: FieldValues; onChange: (values: FieldValues) => void
}) {
  if (!schema) return null
  const fields = schema.editable
  const touched = Object.keys(values).length
  const set = (name: string, value: FieldValues[string] | undefined) => {
    const next = { ...values }
    if (value === undefined) delete next[name]
    else next[name] = value
    onChange(next)
  }
  if (!fields.length) return <p className="record-help">This database has no other properties Koe can fill. Add one below.</p>
  return <details className="record-fields" open={touched > 0}>
    <summary>More properties{touched ? ` · ${touched} changed` : ''}</summary>
    <p className="record-help">Untouched properties keep their current value in Notion.{schema.partial ? ' Only the first 100 properties are shown.' : ''}</p>
    {fields.map(field => {
      const value = values[field.name]
      const id = `field-${field.name.replace(/\W+/g, '-')}`
      const cleared = value === null
      const limitReached = touched >= MAX_FIELDS && !(field.name in values)
      return <div className="record-field" key={field.name} data-touched={field.name in values || undefined}>
        <label htmlFor={id}>{field.name} <small>{field.type.replace('_', ' ')}</small></label>
        <div className="record-field-input">
          {field.type === 'checkbox' ? <select id={id} disabled={limitReached} value={value === undefined ? '' : String(value)}
              onChange={e => set(field.name, e.target.value === '' ? undefined : e.target.value === 'true')}>
              <option value="">Leave as is</option><option value="true">Checked</option><option value="false">Unchecked</option></select>
            : field.type === 'select' || field.type === 'status' ? <select id={id} disabled={limitReached} value={cleared ? '__clear' : typeof value === 'string' ? value : ''}
              onChange={e => set(field.name, e.target.value === '' ? undefined : e.target.value === '__clear' ? null : e.target.value)}>
              <option value="">Leave as is</option>{field.options.map(o => <option key={o} value={o}>{o}</option>)}
              {CLEARABLE.has(field.type) && <option value="__clear">Clear</option>}</select>
            : field.type === 'multi_select' ? <fieldset id={id} className="record-multi" disabled={limitReached} aria-label={field.name}>
              {field.options.map(o => {
                const chosen = Array.isArray(value) ? value : []
                return <label key={o}><input type="checkbox" checked={chosen.includes(o)}
                  onChange={e => set(field.name, e.target.checked ? [...chosen, o] : chosen.filter(c => c !== o))} />{o}</label>
              })}
              {Array.isArray(value) && <button type="button" className="ghost" onClick={() => set(field.name, undefined)}>Leave as is</button>}
            </fieldset>
            : <input id={id} disabled={limitReached || cleared} placeholder={cleared ? 'Will be cleared' : 'Leave as is'}
              type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : field.type === 'url' ? 'url' : field.type === 'email' ? 'email' : 'text'}
              step={field.type === 'number' ? 'any' : undefined} maxLength={field.type === 'number' ? undefined : 1000}
              value={value === undefined || value === null ? '' : String(value)}
              onChange={e => set(field.name, e.target.value === '' ? undefined : field.type === 'number' ? Number(e.target.value) : e.target.value)} />}
          {CLEARABLE.has(field.type) && field.type !== 'select' && field.type !== 'status' && <button type="button" className="ghost"
            onClick={() => set(field.name, cleared ? undefined : null)}>{cleared ? 'Undo' : 'Clear'}</button>}
        </div>
      </div>
    })}
    {touched >= MAX_FIELDS && <p className="record-help">At most {MAX_FIELDS} properties per change.</p>}
  </details>
}

// A new property is a schema change with its own approval (POST /api/notion/proposals, tool notion_add_properties).
// Filling it on records is a separate, later approval. Options: one per line (Notion option names can't contain commas).
const TYPES: [string, string][] = [['rich_text', 'Text'], ['number', 'Number'], ['checkbox', 'Checkbox'], ['date', 'Date'],
  ['url', 'Link'], ['email', 'Email'], ['select', 'Select (one choice)'], ['multi_select', 'Multi-select']]

export function AddPropertyForm({ disabled, onPropose, onClose }: {
  disabled: boolean; onPropose: (property: { name: string; type: string; options?: string[] }) => void; onClose: () => void
}) {
  const [name, setName] = useState('')
  const [type, setType] = useState('rich_text')
  const [options, setOptions] = useState('')
  const choices = type === 'select' || type === 'multi_select'
  const list = options.split('\n').map(o => o.trim()).filter(Boolean)
  const problem = !name.trim() ? '' : name.trim().length > 100 ? 'Names can be up to 100 characters.'
    : choices && !list.length ? 'Add at least one option.' : choices && list.length > 30 ? 'At most 30 options.'
      : choices && list.some(o => o.includes(',')) ? 'Option names can’t contain commas.'
        : choices && new Set(list.map(o => o.toLowerCase())).size !== list.length ? 'Each option must be different.' : ''
  function submit(e: FormEvent) {
    e.preventDefault()
    if (problem || !name.trim()) return
    onPropose({ name: name.trim(), type, ...(choices ? { options: list } : {}) })
  }
  return <form className="record-editor" onSubmit={submit}>
    <div className="record-editor-heading"><h2>Add a property</h2>
      <button className="icon-btn" type="button" aria-label="Close" onClick={onClose}><X /></button></div>
    <label>Name<input required maxLength={100} value={name} onChange={e => setName(e.target.value)} placeholder="Priority" /></label>
    <label>Type<select value={type} onChange={e => setType(e.target.value)}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
    {choices && <label>Options (one per line)<textarea rows={5} value={options} onChange={e => setOptions(e.target.value)} placeholder={'High\nMedium\nLow'} /></label>}
    {problem && <p className="record-help" role="alert">{problem}</p>}
    <p className="record-help">This adds an empty column to your database; existing records aren’t changed. You’ll review it first,
      then you can fill it on records as a separate change.</p>
    <button className="primary" disabled={disabled || !name.trim() || !!problem}><Plus />Preview new property</button>
  </form>
}
