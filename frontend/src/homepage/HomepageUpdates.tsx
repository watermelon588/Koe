import { ArrowUpRight, Check } from '@phosphor-icons/react'

const UPDATES = [
  { number: '01', title: 'Your accounts. A clearer setup.', text: 'Invited users can connect their own Google and GitHub accounts. Check Google access, reconnect when needed, and enable Docs separately. Choose the repositories Koe may use.', link: '/guide#connect', label: 'Get connected' },
  { number: '02', title: 'From a thought to a document.', text: 'Read a Google Doc from its link, create a new document, or prepare a text edit. Correct a timesheet entry or add a column. Each change comes with a preview for your approval.', link: '/guide#documents', label: 'Explore documents & sheets' },
  { number: '03', title: 'Know what you actually shipped.', text: 'Ask for commits and merged pull requests over a date range, contribution streaks, or changed lines when you need them. Koe links to the source and explains any gaps in coverage.', link: '/guide#github', label: 'Find your GitHub activity' },
  { number: '04', title: 'A companion with a little life.', text: 'Meet Kami, Mei or Kobashi in 3D. Move your cursor, wave hello, or drag to turn. Pause movement whenever you like; your reduced-motion preference is respected.', link: '/guide#companion', label: 'Meet your companion' },
] as const

export function HomepageUpdates() {
  return <section className="hp-section hp-container" id="updates" aria-labelledby="hp-updates-title">
    <div className="hp-section-heading hp-reveal"><div><p className="hp-eyebrow">RECENTLY IN KOE / OCTOBER 2026</p><h2 id="hp-updates-title">More of your day.<br /><span>A little easier.</span></h2></div><p>A few more ways to bring work together, with clearer connections and the same final say.</p></div>
    <div className="hp-updates hp-reveal">{UPDATES.map(item => <article key={item.number}>
      <span className="hp-caption">{item.number} /</span><h3>{item.title}</h3><p>{item.text}</p><a className="hp-text-link" href={item.link}>{item.label}<ArrowUpRight size={14} /></a>
    </article>)}</div>
    <p className="hp-updates-note"><Check size={16} aria-hidden="true" /><span>Connections recover when possible. If access expires, Koe asks you to reconnect. Unconfirmed changes are never silently repeated. <a href="/guide#troubleshooting">See the recovery guide.</a></span></p>
  </section>
}
