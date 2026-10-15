import { useEffect, useState, type FormEvent } from 'react'
import { UserPlus, Users } from '@phosphor-icons/react'
import { httpUrl } from '../backend'
import { SettingRow, SettingSection } from './Connections'

// Settings → People (ACCOUNTS_SPEC.md, admin; backend koe/people.py): who may sign in to Koe. Only the owner sees it:
// for anyone else GET /api/people is refused and the section stays hidden. Removing someone signs them out everywhere.
type Person = { email: string; invited: string; joined: boolean }

async function problem(r: Response) {
  return ((await r.json().catch(() => ({}))) as { detail?: string }).detail ?? `Koe answered ${r.status}.`
}

const fetchPeople = (): Promise<Person[] | null> => fetch(httpUrl('/api/people'))
  .then((r) => r.ok ? r.json() as Promise<{ people: Person[] }> : null).then((d) => d?.people ?? null).catch(() => null)

export function PeopleSection() {
  const [people, setPeople] = useState<Person[] | null>(null)
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const load = async () => setPeople(await fetchPeople())
  useEffect(() => { void fetchPeople().then(setPeople) }, [])

  async function invite(e: FormEvent) {
    e.preventDefault()
    setBusy('invite'); setError('')
    const r = await fetch(httpUrl('/api/people'), { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }) }).catch(() => null)
    if (r?.ok) { setEmail(''); await load() } else setError(r ? await problem(r) : 'Koe is offline.')
    setBusy('')
  }

  async function remove(person: string) {
    if (!confirm(`Remove ${person}? They’ll be signed out of Koe on every device.`)) return
    setBusy(person); setError('')
    const r = await fetch(httpUrl(`/api/people/${encodeURIComponent(person)}`), { method: 'DELETE' }).catch(() => null)
    if (r?.ok) await load(); else setError(r ? await problem(r) : 'Koe is offline.')
    setBusy('')
  }

  if (!people) return null
  return (
    <SettingSection id="set-people" title="People" intro="Who can sign in to Koe with Google. Only you see this.">
      {people.map((p) => <SettingRow key={p.email} icon={Users} title={p.email} on={p.joined}
        status={p.joined ? 'Has signed in.' : 'Invited, hasn’t signed in yet.'}
        action={<button className="ghost" disabled={!!busy} onClick={() => void remove(p.email)}>{busy === p.email ? 'Removing…' : 'Remove'}</button>} />)}
      <SettingRow icon={UserPlus} title="Invite someone" status={error || 'They sign in with this Google account. Send them the link yourself.'}>
        <form className="token-row" onSubmit={(e) => void invite(e)}>
          <input type="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="friend@gmail.com" aria-label="Email to invite" autoComplete="off" />
          <button className="soft" disabled={!email.trim() || !!busy}>{busy === 'invite' ? 'Inviting…' : 'Invite'}</button>
        </form>
      </SettingRow>
    </SettingSection>
  )
}
