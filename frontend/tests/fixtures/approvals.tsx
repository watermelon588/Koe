// Local browser acceptance only; this entry is excluded from the production build.
import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ApprovalList, ActivityFeed } from '../../src/dashboard/Dashboard'
import { ApprovalPreview } from '../../src/approvals/ApprovalPreview'
import { ChatPage } from '../../src/chat/ChatPage'
import { NotionPage } from '../../src/notion/NotionPage'
import type { Approval, DashboardState } from '../../src/dashboard/state'
import '../../src/index.css'
import '../../src/dashboard/dashboard.css'

export default function Fixture() {
  const [data, setData] = useState<{ action: Approval; dashboard: DashboardState } | null>(null)
  const [view, setView] = useState('dashboard')
  const [notice, setNotice] = useState('')
  useEffect(() => { fetch('/__s2/fixture').then(r => r.json()).then(setData) }, [])
  async function decide(approve: boolean) {
    const r = await fetch('/__s2/decision', { method: 'POST', body: JSON.stringify({ action_id: data!.action.id, approve }) })
    setNotice((await r.json()).status)
  }
  return <>
    <nav aria-label="Fixture views" style={{ padding: 12, display: 'flex', gap: 8 }}>
      {['dashboard', 'chat', 'notion'].map(v => <button className="ghost" key={v} onClick={() => setView(v)}>{v}</button>)}
    </nav>
    {view === 'chat' ? <ChatPage model="kami" /> : view === 'notion' ? <NotionPage token="synthetic" onToken={() => {}} />
      : data && <main className="dash-page" style={{ paddingTop: 24 }}>
        <h1>Review changes</h1><p role="status">{notice}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: 24, marginTop: 24 }}>
          <section aria-label="Dashboard approval"><h2>Approvals</h2><ApprovalList pending={[data.action]} currentApproval={data.action} decide={decide} /></section>
          <section aria-label="Call approval"><h2>Call</h2><div className="approval-card"><div className="approval-copy"><ApprovalPreview action={data.action} /></div><div className="pair"><button className="ghost" onClick={() => void decide(false)}>Cancel</button><button className="soft" onClick={() => void decide(true)}>Confirm</button></div></div></section>
          <section aria-label="Activity"><h2>Activity</h2><ActivityFeed data={data.dashboard} /></section>
        </div>
      </main>}
  </>
}
createRoot(document.getElementById('root')!).render(<Fixture />)
