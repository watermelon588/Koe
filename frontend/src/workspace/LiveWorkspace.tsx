import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { ArrowSquareOut, CheckCircle, X } from '@phosphor-icons/react'
import { CalendarIcon, DocsIcon, NotionIcon, SheetsIcon } from '../components/BrandIcon'
import { httpUrl } from '../backend'
import { savedToken } from '../chat/api'
import { CalendarWork, DocsWork, NotionWork, SheetsWork } from './WorkViews'
import { announce, clockTime, LABEL, liveUrl, SERVICES, serviceLink, type Account, type Phase, type Service, type WorkCard, type WorkState } from './workState'
import './workspace.css'

// The live workspace (SPEC §2 "Live workspace"): watch Koe work in Calendar, Sheets and Notion, like a browser side
// panel. The chat shows it as a side panel (bottom sheet on phones); a call shows it inline in the call panel.
// Motion is GSAP (useGSAP cleans up on unmount): https://gsap.com/resources/React

gsap.registerPlugin(useGSAP)
const REDUCE = '(prefers-reduced-motion: reduce)'
const WIDE = '(min-width: 900px)'
const ICON = { docs: DocsIcon, calendar: CalendarIcon, sheets: SheetsIcon, notion: NotionIcon }
const PHASE: Record<Phase, string> = { working: 'Checking', preparing: 'Preparing preview', ready: 'Checked',
  waiting: 'Waiting for your confirmation', saving: 'Confirming and saving', saved: 'Saved', cancelled: 'Cancelled', error: 'Needs attention' }
const EMPTY: Record<Service, string> = {
  docs: 'Ask Koe to create a Google Doc or paste an existing Doc link in chat. Review exact text before confirming changes.',
  calendar: 'Ask Koe to check your calendar, find a free slot or book a meeting. The exact slot appears here before you confirm.',
  sheets: 'Ask Koe to log hours for a client. The exact row appears here before you confirm.',
  notion: 'Ask Koe to save a task, note or meeting record, or to log what you shipped. The record appears here.',
}

// Account details for the live view, fetched once (GET /api/connections; same auth header as the chat API).
let account: Promise<Account> | null = null
function loadAccount(): Promise<Account> {
  account ??= fetch(httpUrl('/api/connections'), { headers: { Authorization: `Bearer ${savedToken()}` } })
    .then(r => (r.ok ? r.json() : null))
    .then(b => ({ timesheet: b?.timesheet ?? '', google: b?.connections?.find((c: { provider: string }) => c.provider === 'google')?.account ?? '' }))
    .catch(() => ({ timesheet: '', google: '' }))
  account.then(a => { if (!a.google && !a.timesheet) account = null }) // not connected yet: ask again next time
  return account
}

export type Decision = { deciding: boolean; decide: (approve: boolean) => void } | null

type Props = {
  work: WorkState
  inline?: boolean // inside the call panel; otherwise a side panel / bottom sheet
  open?: boolean
  onClose?: () => void
  decision: (actionId: string) => Decision // the existing Confirm/Cancel of the chat or call, for this proposal
  headingRef?: RefObject<HTMLHeadingElement | null>
}

export function LiveWorkspace({ work, inline = false, open = true, onClose, decision, headingRef }: Props) {
  const root = useRef<HTMLElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const ownHeading = useRef<HTMLHeadingElement>(null)
  const heading = headingRef ?? ownHeading
  const [chosen, setChosen] = useState<{ service: Service; revision: number } | null>(null)
  const service: Service = chosen?.revision === work.revision ? chosen.service : work.active ?? chosen?.service ?? 'calendar'
  const [acct, setAcct] = useState<Account | null>(null)
  const card = work[service]
  // A new proposal or failure always shows Koe's view: the exact pending item (Google/Notion can't show it until it's
  // saved) or the provider's error and hint.
  const [pick, setPick] = useState<{ view: 'koe' | 'live'; revision: number }>({ view: 'koe', revision: -1 })
  const view = (card?.phase === 'waiting' || card?.phase === 'error') && pick.revision !== work.revision ? 'koe' : pick.view
  const setView = (v: 'koe' | 'live') => setPick({ view: v, revision: work.revision })
  const visible = inline || open
  const canFrame = service === 'calendar' || service === 'sheets'
  const live = view === 'live' && canFrame && visible
  useEffect(() => { if (live && !acct) void loadAccount().then(setAcct) }, [live, acct])

  // Panel in/out: slides from the right on wide screens, up from the bottom on phones. First paint is instant.
  const first = useRef(true)
  useGSAP(() => {
    const el = root.current
    if (!el) return
    const reduce = matchMedia(REDUCE).matches
    const instant = first.current || reduce
    first.current = false
    if (inline) { // the call's Work tab just opened: slide the workspace in
      if (!reduce) gsap.fromTo(el, { x: 18, autoAlpha: 0 }, { x: 0, autoAlpha: 1, duration: 0.42, ease: 'expo.out' })
      return
    }
    const hidden = matchMedia(WIDE).matches ? { xPercent: 104, yPercent: 0 } : { xPercent: 0, yPercent: 104 }
    if (open) gsap.set(el, { visibility: 'inherit' }) // focusable now (the opener moves focus next frame), still off-screen
    gsap.to(el, open ? { xPercent: 0, yPercent: 0, autoAlpha: 1, duration: instant ? 0 : 0.5, ease: 'expo.out', overwrite: true }
      : { ...hidden, autoAlpha: 0, duration: instant ? 0 : 0.26, ease: 'power2.in', overwrite: true })
  }, { dependencies: [open, inline], scope: root })

  // The authored moment: a proposal settles in; a confirmed write drops into place, pulses, then the receipt and its
  // check mark land. Only transform/opacity. Reduced motion: everything is simply there.
  const phase = card?.phase
  useGSAP(() => {
    if (!visible || view !== 'koe' || !phase) return
    const target = body.current?.querySelector<HTMLElement>('.lw-target')
    if (target && body.current) { // e.g. a 7 pm slot below the fold of the day timeline: scroll the panel, not the page
      const a = target.getBoundingClientRect(), b = body.current.getBoundingClientRect()
      const top = b.top + (body.current.querySelector<HTMLElement>('.lw-receipt')?.offsetHeight ?? 0) // under the sticky receipt
      if (a.top < top || a.bottom > b.bottom) body.current.scrollTop += a.top - top - (b.bottom - top - a.height) / 2
    }
    if (matchMedia(REDUCE).matches) return
    if (phase === 'waiting' && target) {
      gsap.fromTo(target, { y: -8, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.4, ease: 'expo.out' })
    }
    if (phase !== 'saved') return
    const flash = body.current?.querySelector<HTMLElement>('.lw-flash')
    const tl = gsap.timeline({ defaults: { ease: 'expo.out' } })
    if (target) {
      tl.fromTo(target, { y: service === 'calendar' ? -28 : -14, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.55 })
      if (flash && body.current) { // a soft accent wash over exactly the saved item
        const a = target.getBoundingClientRect(), b = body.current.getBoundingClientRect()
        gsap.set(flash, { x: a.left - b.left, y: a.top - b.top + body.current.scrollTop, width: a.width, height: a.height })
        tl.fromTo(flash, { autoAlpha: 0 }, { autoAlpha: 0.3, duration: 0.18, ease: 'power1.out' }, '-=0.15')
          .to(flash, { autoAlpha: 0, duration: 0.7, ease: 'power2.out' })
      }
    }
    // fromTo, not from: if this re-runs mid-flight, from() would capture the half-faded state as its end state.
    tl.fromTo('.lw-receipt', { y: 10, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.4 }, target ? '-=0.75' : 0)
      .fromTo('.lw-check', { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.45, ease: 'back.out(2.2)' }, '<0.1')
  }, { dependencies: [service, phase, card?.work.action_id, card?.operationId, view, visible], scope: root })

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape' && onClose) { e.stopPropagation(); onClose() }
  }

  const Icon = ICON[service]
  const url = serviceLink(card?.work.url, service)
  const frame = live && acct ? liveUrl(service, card?.work, acct) : ''
  const choice = card?.phase === 'waiting' && card.work.action_id ? decision(card.work.action_id) : null
  return (
    <aside ref={root} id="live-workspace" className="lw" data-inline={inline || undefined} aria-labelledby="lw-title"
      inert={!visible} onKeyDown={onKeyDown}>
      <header className="lw-head">
        <h2 id="lw-title" ref={heading} tabIndex={-1}><Icon size={20} />{LABEL[service]}</h2>
        <div className="lw-actions">
          {url && <a className="soft lw-open" href={url} target="_blank" rel="noreferrer" aria-label={`Open in ${LABEL[service]}`}><ArrowSquareOut size={16} /><span>Open<span className="lw-wide-only"> in {LABEL[service]}</span></span></a>}
          {onClose && <button className="icon-btn" onClick={onClose} aria-label="Close live workspace" title="Close (Esc)"><X /></button>}
        </div>
      </header>
      <div className="lw-bar">
        <div className="seg" role="group" aria-label="Service">
          {SERVICES.map(s => {
            const S = ICON[s]
            return <button key={s} aria-pressed={s === service} onClick={() => setChosen({ service: s, revision: work.revision })}>
              <S size={14} />{s === 'calendar' ? 'Calendar' : s === 'sheets' ? 'Sheets' : s === 'docs' ? 'Docs' : 'Notion'}{work[s] && <i className="lw-dot" data-phase={work[s]!.phase} aria-hidden="true" />}</button>
          })}
        </div>
        <div className="seg" role="group" aria-label="View">
          <button aria-pressed={view === 'koe'} onClick={() => setView('koe')}>Koe’s view</button>
          <button aria-pressed={view === 'live'} onClick={() => setView('live')}>Live view</button>
        </div>
      </div>
      {card && <p className="work-phase lw-phase" data-phase={card.phase}><span aria-hidden="true" />{PHASE[card.phase]}</p>}
      <p className="lw-sr" aria-live="polite">{announce(service, card)}</p>

      <div className="lw-body" ref={body}>
        <span className="lw-flash" aria-hidden="true" />
        {view === 'live' ? <>
          {card?.phase === 'saved' && <Receipt card={card} service={service} url={url} />}
          <LiveView service={service} frame={frame} loading={live && !acct} url={url} revision={work.revision} />
        </>
          : !card ? <div className="lw-empty"><Icon size={30} /><p>{EMPTY[service]}</p></div>
          : <>
            {card.work.error && <div className="work-error" role="alert"><p>{card.work.error.message}</p>{card.work.error.hint && <p>{card.work.error.hint}</p>}</div>}
            {card.phase === 'saved' && <Receipt card={card} service={service} url={url} />}
            {service === 'calendar' ? <CalendarWork card={card} /> : service === 'sheets' ? <SheetsWork card={card} /> : service === 'docs' ? <DocsWork card={card} /> : <NotionWork card={card} />}
          </>}
      </div>

      {card?.phase === 'waiting' && <footer className="lw-decide">
        <p>Nothing is saved until you confirm.{!choice && ' Use the Confirm button in the conversation, or say yes or no.'}</p>
        {choice && <div className="pair">
          <button className="ghost" disabled={choice.deciding} onClick={() => choice.decide(false)}>Cancel</button>
          <button className="primary" disabled={choice.deciding} onClick={() => choice.decide(true)}>{choice.deciding ? 'Checking…' : 'Confirm'}</button>
        </div>}
      </footer>}
      {card?.phase === 'saving' && <footer className="lw-decide"><p>Checking your decision and waiting for {LABEL[service]} to confirm…</p></footer>}
    </aside>
  )
}

// The exact identifiers of what was written, so "did it really save?" has one answer.
function Receipt({ card, service, url }: { card: WorkCard; service: Service; url: string }) {
  const { work } = card
  const d = work.details
  const lines = service === 'docs' ? [['Document', work.title || d.title || '—'], ['Tab', d.tab_title || 'First tab'], ['Result', work.message || 'Saved']] : service === 'sheets' ? [['Row', String(work.row ?? '—')], ['Range', work.range ?? '—'], ['Tab', d.sheet_name ?? '—']]
    : service === 'calendar' ? [['Event', work.title || d.title || '—'], ['When', d.start && d.end ? `${d.start.slice(0, 10)} · ${clockTime(d.start, work.timezone)} – ${clockTime(d.end, work.timezone)}` : '—'],
      ['Time zone', work.timezone ?? '—']]
      : [['Page', work.title || d.title || `Daily log · ${d.date}`], ['Type', work.kind || d.kind || (work.operation === 'notion_log' ? 'Daily log' : '—')],
        ...(work.operation === 'notion_log' ? [['Added', `${work.added ?? 0} new entr${work.added === 1 ? 'y' : 'ies'}`]] : [])]
  return <section className="lw-receipt" aria-label="Saved">
    <CheckCircle className="lw-check" size={26} weight="light" />
    <div>
      <h3>{service === 'docs' ? 'Saved in Google Docs' : service === 'sheets' ? 'Row appended' : service === 'calendar' ? (d.event_id ? 'Event moved' : 'Event booked') : work.operation === 'notion_archive' ? 'Moved to trash' : 'Saved in Notion'}</h3>
      <dl>{lines.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      {url ? <a href={url} target="_blank" rel="noreferrer">Open in {LABEL[service]} <ArrowSquareOut size={13} /></a>
        : <small>{LABEL[service]} returned no link.</small>}
    </div>
  </section>
}

function LiveView({ service, frame, loading, url, revision }: { service: Service; frame: string; loading: boolean; url: string; revision: number }) {
  if (service === 'docs') return <div className="lw-empty"><DocsIcon size={30} /><p>Koe’s view shows the text and changes. Open Google Docs for the full editor.</p>{url && <a className="soft" href={url} target="_blank" rel="noreferrer">Open in Google Docs</a>}</div>
  if (service === 'notion') return <div className="lw-empty"><NotionIcon size={30} />
    <p>Notion doesn’t allow its pages inside other sites (it sends X-Frame-Options: SAMEORIGIN), so there’s no live view. Koe’s view shows the record as Notion returned it.</p>
    {url && <a className="soft" href={url} target="_blank" rel="noreferrer"><ArrowSquareOut size={16} />Open in Notion</a>}</div>
  if (loading) return <div className="lw-empty"><p>Finding your {LABEL[service]}…</p></div>
  if (!frame) return <div className="lw-empty"><p>{service === 'sheets' ? 'No timesheet yet. Create one in Settings → Connections.' : 'Connect Google in Settings → Connections to see your calendar here.'}</p></div>
  return <div className="lw-live">
    {/* Lazy, sandboxed (no top-level navigation), and only a calendar address or sheet ID in the URL, never a token.
        Reloads after each change so the new row/event shows. */}
    <iframe key={`${frame}#${revision}`} src={frame} title={`${LABEL[service]} live view`} loading="lazy" referrerPolicy="no-referrer"
      sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-forms allow-storage-access-by-user-activation" />
    <p className="lw-muted">This is Google’s own page. It shows your data only if this browser is signed in to Google (and allows Google’s cookies inside other sites). Blank, or asking you to sign in? Use Koe’s view or {url ? <a href={url} target="_blank" rel="noreferrer">open it in a tab</a> : 'open it in a new tab'}.</p>
  </div>
}
