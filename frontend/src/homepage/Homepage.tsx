import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { ArrowDown, ArrowRight, ArrowUpRight, Check, CheckCircle, Clock, Cube, Image,
  GitPullRequest, HandWaving, Headphones, LockKey, Microphone, Play, ShieldCheck, Sparkle, X } from '@phosphor-icons/react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { BrandIcon, type Brand } from '../components/BrandIcon'
import { MascotView, type MascotController } from '../mascot/MascotView'
import { MASCOTS } from '../mascot/catalog'
import { HOMEPAGE_ART, type HomepageMascotId } from './artwork'
import './fonts.css'
import './homepage.css'
import './interactions.css'

gsap.registerPlugin(useGSAP, ScrollTrigger)

const HOME_MASCOTS = MASCOTS.filter(item => item.id !== 'aoi')

const INTEGRATIONS: { id: Brand; name: string; category: string; description: string; planned?: boolean; features: string[] }[] = [
  { id: 'github', name: 'GitHub', category: 'DEVELOPMENT', description: 'Know what needs your review, why CI failed, and what you shipped.', features: ['Your review queue and pull request status', 'Plain-English diff summaries with risk notes', 'Comments proposed for your approval'] },
  { id: 'calendar', name: 'Google Calendar', category: 'YOUR SCHEDULE', description: 'Find a real opening. Book the right meeting. Keep your focus time.', features: ['Read your day and find free windows', 'Preview the date, time zone, and attendees', 'Approve before a booking or reschedule'] },
  { id: 'notion', name: 'Notion', category: 'KNOWLEDGE & TASKS', description: 'Turn a passing thought into a task, a note, or a meeting record.', features: ['Search and preview your workspace records', 'Create and update tasks, notes, and meeting records', 'Review changes before saving or archiving'] },
  { id: 'sheets', name: 'Google Sheets', category: 'THE SMALL ADMIN', description: 'Log your hours while the work is still fresh in your mind.', features: ['A dedicated timesheet in your Google account', 'Date, client, hours, and a clear work note', 'An exact row preview before every approved entry'] },
  { id: 'spotify', name: 'Spotify', category: 'YOUR FOCUS SOUNDTRACK', description: 'Your own playlists, right beside your work. Private by design.', features: ['Manual playlist and playback controls', 'Music pauses before calls and recordings', 'Music and listening activity stay outside the AI'] },
  { id: 'docs', name: 'Google Docs', category: 'DOCUMENTS', description: 'Create a document or refine a passage, in the same conversation.', features: ['Enable Docs in Settings with your Google account', 'Read a Doc link, create documents and edit plain text', 'Review every change before Koe saves it'] },
]

const SCENARIOS = [
  { id: 'morning', label: 'Start my day', prompt: '“What needs my attention today?”', reply: 'You have 2 pull requests waiting for review and a design sync at 11. There’s a clear window before lunch.', service: 'github' as Brand, title: 'A little clarity for your morning.', items: [ ['Review the authentication update', 'GitHub · PR #42 · checks passing'], ['Design sync', 'Google Calendar · 11:00–11:30'], ['A moment to focus', 'Free window · 11:30–13:00'] ], foot: 'Your work, brought into one conversation.' },
  { id: 'meeting', label: 'Find a time', prompt: '“Find 30 minutes for a project catch-up.”', reply: 'There’s a free slot tomorrow at 2 PM. Here’s the proposed event. You can confirm it in your workspace.', service: 'calendar' as Brand, title: 'A meeting, without the back-and-forth.', items: [ ['Project catch-up', 'Google Calendar · proposed event'], ['Tomorrow · 14:00–14:30', 'Asia/Kolkata · 30 minutes'], ['Waiting for your approval', 'Review the exact event before it is booked'] ], foot: 'Nothing is booked until you approve.' },
  { id: 'capture', label: 'Capture a thought', prompt: '“Make a task to tidy up the onboarding flow.”', reply: 'I’ve prepared an onboarding task in Notion. Take a look at the title and details before you save it.', service: 'notion' as Brand, title: 'Good ideas deserve a place to land.', items: [ ['Tidy up the onboarding flow', 'Notion · proposed task'], ['Small details, less friction', 'Review the first-run experience'], ['Ready when you are', 'Confirm to save this task to your workspace'] ], foot: 'A thought becomes a record, with your OK.' },
] as const

const FAQS = [
  ['What can I actually ask Koe to do?', 'Ask about your GitHub reviews and CI, find a free window in your calendar, prepare a meeting, capture a Notion task or note, or log hours in Sheets. Consequential changes are shown for your approval. Spotify has separate manual controls.'],
  ['Does Koe make changes without asking?', 'Meetings, GitHub comments, timesheet entries, and Notion edits or archiving require your approval. Appending to your own daily development log is the existing low-risk exception. You can see proposed changes before they run.'],
  ['Do I have to use my voice?', 'No. Use a live voice call, type in chat, or record a voice note in the app. The installable web app works on your phone too. WhatsApp is a separate channel that depends on the owner’s Meta setup.'],
  ['Which connections are available today?', 'GitHub, Google Calendar, Notion, Google Sheets, and optional Spotify are implemented. Availability depends on provider credentials and account permissions. Google Docs supports creation and text editing after you enable its additional permissions. Drive is used only to find app-accessible Docs.'],
  ['Who can use Koe right now?', 'Koe is a personal project with invite-only access when sign-in is enabled. Open the app to sign in with an invited Google account. There is no public signup or paid plan advertised here.'],
  ['What happens to my accounts and music?', 'Provider credentials stay on the backend. You choose the services to connect and can disconnect them in Settings. Spotify metadata and audio do not enter AI prompts or transcripts. See the Privacy page for the complete data flow.'],
] as const

const companionName = (id: HomepageMascotId) => HOME_MASCOTS.find(item => item.id === id)!.name

function Waveform({ small = false }: { small?: boolean }) {
  return <span className={`hp-waveform ${small ? 'hp-waveform--small' : ''}`} aria-hidden="true">
    {[9, 18, 27, 14, 32, 23, 36, 18, 29, 12, 24, 15, 8].map((height, index) => <i key={index} style={{ '--wave-height': `${height}px`, '--wave-delay': `${index * 45}ms` } as CSSProperties} />)}
  </span>
}

function DemoWorkspace() {
  const [scenario, setScenario] = useState(0)
  const [confirmed, setConfirmed] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const item = SCENARIOS[scenario]
  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.hp-demo-change', { y: 10, opacity: 0, duration: .4, stagger: .06, ease: 'power2.out' })
    })
    return () => media.revert()
  }, { scope: root, dependencies: [scenario], revertOnUpdate: true })
  return <div className="hp-demo" ref={root}>
    <div className="hp-demo-top"><span><span className="hp-dot" /> Your workspace, in conversation</span><span className="hp-demo-label">INTERACTIVE DEMO</span></div>
    <div className="hp-demo-tabs" role="group" aria-label="Example workflow">
      {SCENARIOS.map((example, index) => <button key={example.id} aria-pressed={scenario === index} onClick={() => { setScenario(index); setConfirmed(false) }}>{example.label}<ArrowUpRight size={14} /></button>)}
    </div>
    <div className="hp-demo-body" aria-live="polite" aria-atomic="true">
      <div className="hp-demo-chat"><span className="hp-caption">YOU SAY</span><p className="hp-demo-prompt hp-demo-change">{item.prompt}</p>
        <div className="hp-demo-answer hp-demo-change"><img src="/mascot/portraits/kami.jpg" width="34" height="34" alt="Kami" /><div><span>Koe</span><p>{item.reply}</p></div></div>
        <div className="hp-demo-input"><Microphone size={18} /><span>A conversation. A clearer day.</span><Waveform small /></div>
      </div>
      <div className="hp-demo-result hp-demo-change"><div className="hp-demo-result-head"><BrandIcon brand={item.service} size={23} /><span>{item.title}</span></div>
        {item.items.map(([title, detail], index) => <div className="hp-demo-row" key={title}><span className="hp-result-symbol">{index === 0 ? <GitPullRequest size={17} /> : index === 1 ? <Clock size={17} /> : <CheckCircle size={17} />}</span><div><p>{title}</p><small>{detail}</small></div></div>)}
        <div className="hp-demo-result-foot">{scenario !== 0 ? <><span>{confirmed ? 'Example approved. No real changes made.' : item.foot}</span><button className="hp-demo-confirm" disabled={confirmed} onClick={() => setConfirmed(true)}><Check size={14} />{confirmed ? 'Approved in demo' : 'Try approving'}</button></> : <><ShieldCheck size={16} /><span>{item.foot}</span></>}</div>
      </div>
    </div>
    <p className="hp-demo-disclaimer">Illustrative examples only. No account access, real bookings, or saved records.</p>
  </div>
}

export function Homepage() {
  const [model, setModel] = useState<HomepageMascotId>('kami')
  const [livePreview, setLivePreview] = useState(false)
  const [greeted, setGreeted] = useState(false)
  const [mascotReady, setMascotReady] = useState(false)
  const [filter, setFilter] = useState<'all' | 'available' | 'planned'>('all')
  const [selected, setSelected] = useState<(typeof INTEGRATIONS)[number] | null>(null)
  const mascot = useRef<MascotController | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const scene = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const url = new URL(location.href)
    if (url.searchParams.has('look')) {
      url.searchParams.delete('look')
      history.replaceState(null, '', url)
    }
    const previous = document.documentElement.dataset.theme
    document.documentElement.dataset.theme = 'light'
    return () => { document.documentElement.dataset.theme = previous }
  }, [])

  const { contextSafe } = useGSAP(() => {
    // MatchMedia also removes animations immediately when the OS motion preference changes.
    // https://gsap.com/resources/React/ and https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('.hp-hero-enter', { y: 24, opacity: 0, duration: .85, stagger: .09, ease: 'power3.out', clearProps: 'transform,opacity' })
      root.current?.querySelectorAll('.hp-reveal').forEach(element => {
        gsap.from(element, { y: 26, opacity: 0, duration: .75, ease: 'power2.out', clearProps: 'transform,opacity', scrollTrigger: { trigger: element, start: 'top 94%', once: true } })
      })
    })
    return () => media.revert()
  }, { scope: root })

  useEffect(() => {
    if (selected) dialog.current?.showModal()
  }, [selected])

  useEffect(() => { ScrollTrigger.refresh() }, [filter])

  function closeDialog() { dialog.current?.close(); setSelected(null) }

  function greet() {
    setGreeted(true)
    if (livePreview) mascot.current?.gesture('wave')
    else if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
      contextSafe(() => {
        gsap.to('.hp-mascot-art', { y: -10, rotation: 2, duration: .22, repeat: 1, yoyo: true, ease: 'power2.out', overwrite: true, clearProps: 'transform' })
      })()
    }
  }

  return <div className="hp" data-look="studio" ref={root}>
    <a className="hp-skip" href="#hp-main">Skip to content</a>
    <header className="hp-header hp-container">
      <a className="hp-brand" href="/" aria-label="Koe homepage">koe<span lang="ja">声</span><span className="hp-brand-dot" /></a>
      <nav aria-label="Homepage navigation"><a href="#product">The experience</a><a href="#connections">Connections</a><a href="#companion">Your companion</a></nav>
      <a className="hp-nav-cta" href="/app">Open app <ArrowUpRight size={15} /></a>
    </header>

    <main id="hp-main">
      <section className="hp-hero hp-container" aria-labelledby="hp-title">
        <div className="hp-hero-copy">
          <p className="hp-eyebrow hp-hero-enter"><span className="hp-dot" /> A LITTLE COMPANY. A LOT LESS BUSYWORK.</p>
          <h1 id="hp-title" className="hp-hero-enter">Less juggling.<br /><span>More doing.</span></h1>
          <p className="hp-hero-description hp-hero-enter">Your work lives in a dozen tabs.<br className="hp-desktop-break" /> Bring it together in one conversation.</p>
          <p className="hp-hero-detail hp-hero-enter">Meet Koe, your voice-first companion for pull requests, plans, and all the little things in between.</p>
          <div className="hp-hero-actions hp-hero-enter"><a className="hp-button" href="/app"><Microphone size={17} />Meet your companion <ArrowRight size={17} /></a><a className="hp-text-link" href="#product"><Play size={13} weight="fill" />See it in action</a></div>
          <p className="hp-hero-fine hp-hero-enter"><ShieldCheck size={14} />Your accounts. Your approval. Your pace.</p>
        </div>

        <div className="hp-scene hp-hero-enter" ref={scene} data-ready={!livePreview || mascotReady} data-live={livePreview} data-mascot={model}>
          <span className="hp-scene-index">A COMPANION FOR YOUR EVERYDAY / 01</span>
          <div className="hp-orbit hp-orbit--one" /><div className="hp-orbit hp-orbit--two" />
          <div className="hp-scene-halo" />
          <div className="hp-mascot-frame">
            <img key={HOMEPAGE_ART[model]} className="hp-mascot-art" src={HOMEPAGE_ART[model]} width="944" height="743" fetchPriority="high" decoding="async" alt={`${companionName(model)}, Koe’s anime companion`} />
            {livePreview && <MascotView model={model} controller={mascot} shot="bust" x={.5} onStatus={status => setMascotReady(status === 'ready')} />}
          </div>
          <div className="hp-orbit-icon hp-orbit-icon--notion"><BrandIcon brand="notion" size={25} /></div>
          <div className="hp-orbit-icon hp-orbit-icon--github"><BrandIcon brand="github" size={27} /></div>
          <div className="hp-orbit-icon hp-orbit-icon--calendar"><BrandIcon brand="calendar" size={26} /></div>
          <div className="hp-scene-note hp-scene-note--task"><span className="hp-tiny-icon"><Check size={14} /></span><div><span>A little less on your plate.</span><small>Tasks, notes, and plans. Together.</small></div></div>
          <div className="hp-scene-greeting"><span className="hp-dot" /><span>{greeted ? 'Hey there. Let’s make today lighter.' : 'Hey, I’m ' + companionName(model) + '.'}</span><button aria-label={`Say hello to ${companionName(model)}`} title="Say hello" disabled={livePreview && !mascotReady} onClick={greet}><HandWaving size={18} /></button></div>
          <div className="hp-scene-bottom"><button className="hp-preview-toggle" aria-pressed={livePreview} onClick={() => { setMascotReady(false); setLivePreview(value => !value) }}>{livePreview ? <Image size={13} /> : <Cube size={13} />}{livePreview ? 'BACK TO ARTWORK' : 'TRY IN 3D'}</button><Waveform small /></div>
        </div>
        <div className="hp-hero-bottom"><span>A calmer way to get things done.</span><a href="#connections">MADE FOR YOUR WORLD <ArrowDown size={13} /></a><span className="hp-hero-edition">THE EVERYDAY EDITION</span></div>
      </section>

      <section className="hp-logo-section hp-container hp-reveal" aria-label="Supported tools"><p>Good company for the tools you already love.</p><div className="hp-logo-strip">{INTEGRATIONS.filter(item => !item.planned).map(item => <a key={item.id} href="#connections"><BrandIcon brand={item.id} size={25} /><span>{item.name.replace('Google ', '')}</span></a>)}</div></section>

      <section className="hp-section hp-container" id="product" aria-labelledby="hp-product-title">
        <div className="hp-section-heading hp-reveal"><div><p className="hp-eyebrow"><span className="hp-section-number">01 /</span> LESS FRICTION, MORE FLOW</p><h2 id="hp-product-title">You say the word.<br /><span>Koe connects the dots.</span></h2></div><p>Skip the tab-hopping. Ask naturally, see what’s happening, and stay in charge of what happens next.</p></div>
        <div className="hp-reveal"><DemoWorkspace /></div>
        <div className="hp-workflow hp-reveal"><div><span>01</span><h3>Start with a thought.</h3><p>Say it, type it, or leave a voice note. No special commands to remember.</p></div><div><span>02</span><h3>Let Koe do the finding.</h3><p>The right pull request, a free slot, that note. Your tools become one workspace.</p></div><div><span>03</span><h3>Give it your OK.</h3><p>Review the important changes before they happen. A little help, with you in control.</p></div></div>
      </section>

      <section className="hp-numbers hp-container hp-reveal" aria-label="Koe in numbers"><div><span>{String(INTEGRATIONS.length).padStart(2, '0')}<span> / services</span></span><p>Your everyday tools, brought together.</p></div><div><span>03<span> / ways to ask</span></span><p>Live voice, typed chat, or a voice note.</p></div><div><span>03<span> / companions</span></span><p>A familiar face that feels like you.</p></div><div><span>01<span> / final say</span></span><p>Yours. For every consequential change.</p></div></section>

      <section className="hp-section hp-container" id="connections" aria-labelledby="hp-connections-title">
        <div className="hp-section-heading hp-reveal"><div><p className="hp-eyebrow"><span className="hp-section-number">02 /</span> YOUR TOOLS, ON SPEAKING TERMS</p><h2 id="hp-connections-title">Same tools.<br /><span>A lot less switching.</span></h2></div><p>Keep the setup you’ve made your own. Connect what you need, and let the small things take care of themselves.</p></div>
        <div className="hp-integration-toolbar hp-reveal"><span>Small connections. Useful possibilities.</span><div role="group" aria-label="Filter connections">{([['all', 'All connections', String(INTEGRATIONS.length).padStart(2, '0')], ['available', 'Available', String(INTEGRATIONS.filter(i => !i.planned).length).padStart(2, '0')], ['planned', 'Coming next', String(INTEGRATIONS.filter(i => i.planned).length).padStart(2, '0')]] as const).filter(([, , count]) => count !== '00').map(([value, label, count]) => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}<span>{count}</span></button>)}</div></div>
        <div className="hp-integrations" aria-live="polite">{INTEGRATIONS.filter(item => filter === 'all' || (filter === 'planned' ? item.planned : !item.planned)).map(item => <button className="hp-integration" key={item.id} onClick={() => setSelected(item)} aria-label={`Learn about ${item.name}${item.planned ? ', planned integration' : ''}`}><div className="hp-integration-top"><span className="hp-integration-logo"><BrandIcon brand={item.id} size={30} /></span><span className={`hp-availability ${item.planned ? 'hp-availability--planned' : ''}`}>{item.planned ? 'On the horizon' : 'Available'}{!item.planned && <span className="hp-dot" />}</span></div><span className="hp-caption">{item.category}</span><h3>{item.name}<ArrowUpRight size={18} /></h3><p>{item.description}</p><span className="hp-integration-more">{item.planned ? 'See what’s planned' : 'Explore the possibilities'}<ArrowRight size={15} /></span></button>)}</div>
        <p className="hp-integrations-foot"><LockKey size={14} />Connect only what you want. Disconnect whenever you need. Availability depends on your account setup.</p>
      </section>

      <section className="hp-companion hp-container hp-reveal" id="companion" aria-labelledby="hp-companion-title">
        <div className="hp-companion-art"><span className="hp-caption">A FAMILIAR FACE / NOT JUST AN INTERFACE</span><div className="hp-companion-portraits">{HOME_MASCOTS.map((item, index) => <button key={item.id} className="hp-portrait" data-active={model === item.id} data-mascot={item.id} style={{ '--portrait-index': index } as CSSProperties} aria-label={`Preview ${companionName(item.id)}`} aria-pressed={model === item.id} onClick={() => { setModel(item.id); setGreeted(false); setMascotReady(false) }}><img src={HOMEPAGE_ART[item.id]} width="944" height="743" loading="lazy" alt={companionName(item.id)} /><span>{companionName(item.id)}<span>{model === item.id ? 'SELECTED' : 'MEET ME'}</span></span></button>)}</div><p>Pick a face above, then meet them at the top of the page. <a href="#hp-title">Say hello <ArrowUpRight size={13} /></a></p></div>
        <div className="hp-companion-copy"><p className="hp-eyebrow"><span className="hp-section-number">03 /</span> A LITTLE MORE HUMAN</p><h2 id="hp-companion-title">A companion.<br /><span>With a little character.</span></h2><p>Work can feel solitary. Your assistant doesn’t have to. Meet an expressive companion who listens, reacts, and makes the everyday a little warmer.</p><ul><li><Check size={15} />An interactive 3D character, not a static avatar</li><li><Check size={15} />Natural gestures and expressions during calls</li><li><Check size={15} />Three different looks to make your space your own</li></ul><a className="hp-text-link" href="/app/settings">Find your companion <ArrowUpRight size={15} /></a></div>
      </section>

      <section className="hp-trust hp-container hp-reveal" aria-labelledby="hp-trust-title"><div><ShieldCheck size={31} weight="light" /><p className="hp-eyebrow">HELPFUL BY NATURE. CONSIDERATE BY DESIGN.</p><h2 id="hp-trust-title">A helping hand.<br /><span>You’re still at the wheel.</span></h2></div><div className="hp-trust-details"><article><LockKey size={20} /><div><h3>Your accounts stay yours.</h3><p>Connect your own services. Credentials stay on the backend, and you choose what Koe can access.</p></div></article><article><CheckCircle size={20} /><div><h3>See it. Then say yes.</h3><p>Meetings, comments, timesheet entries, and Notion edits wait for your approval. Own daily logs can append automatically.</p></div></article><article><Headphones size={20} /><div><h3>Your soundtrack stays private.</h3><p>Spotify lives beside the assistant. Your listening never becomes part of its prompts or transcripts.</p></div></article><a className="hp-text-link" href="/privacy">A closer look at privacy <ArrowUpRight size={14} /></a></div></section>

      <section className="hp-faq hp-container hp-reveal" id="questions" aria-labelledby="hp-faq-title"><div><p className="hp-eyebrow"><span className="hp-section-number">04 /</span> A FEW GOOD QUESTIONS</p><h2 id="hp-faq-title">Before you<br /><span>say hello.</span></h2><p>Curious about the details?<br /><a href="/guide">Take a look around the guide <ArrowUpRight size={13} /></a></p></div><div className="hp-faq-list">{FAQS.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>

      <section className="hp-closing hp-container hp-reveal"><div className="hp-closing-top"><span className="hp-eyebrow"><span className="hp-dot" /> GOOD WORK STARTS WITH A CONVERSATION.</span><Sparkle size={24} weight="light" /></div><h2>A little less busy.<br /><span>A little more you.</span></h2><div className="hp-closing-bottom"><p>Your next idea, your next meeting, your next small win.<br />You don’t have to juggle it all alone.</p><a className="hp-button" href="/app">Say hello to Koe <ArrowUpRight size={18} /></a></div><span className="hp-closing-note">A personal project. Currently invite only.</span></section>
    </main>

    <footer className="hp-footer hp-container"><div><a className="hp-brand" href="/">koe<span lang="ja">声</span><span className="hp-brand-dot" /></a><p>A little company for the work ahead.</p></div><nav aria-label="Footer navigation"><a href="/guide">Guide</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="/app/install">Install the app <ArrowUpRight size={12} /></a></nav><span>MADE WITH CARE. BUILT FOR EVERYDAY.</span></footer>


    <dialog className="hp-connection-dialog" ref={dialog} onCancel={() => setSelected(null)} onClose={() => setSelected(null)} onClick={event => { if (event.target === event.currentTarget) closeDialog() }} aria-labelledby="hp-dialog-title">{selected && <><button className="hp-dialog-close" aria-label="Close connection details" onClick={closeDialog}><X size={20} /></button><BrandIcon brand={selected.id} size={42} /><p className="hp-eyebrow">{selected.planned ? 'COMING NEXT' : 'MAKE THE CONNECTION'}</p><h2 id="hp-dialog-title">{selected.name}</h2><p>{selected.description}</p><ul>{selected.features.map(feature => <li key={feature}><CheckCircle size={18} />{feature}</li>)}</ul>{selected.planned ? <p className="hp-dialog-note">This connection is planned. You cannot connect it yet.</p> : <a className="hp-button" href={selected.id === 'spotify' ? '/app/music' : '/app/settings'}>Manage in the app <ArrowUpRight size={16} /></a>}</>}</dialog>
  </div>
}
