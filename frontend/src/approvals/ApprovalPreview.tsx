import { providerLink, type ReviewAction } from './presentation'
import './approvals.css'
import { BrandIcon } from '../components/BrandIcon'
import { brandForUrl } from '../components/brandForUrl'

export function AuditDetails({ summary }: { summary: string }) {
  return <details className="action-audit"><summary>Details</summary><pre>{summary}</pre></details>
}

export function ApprovalPreview({ action }: { action: ReviewAction }) {
  const display = action.display
  const url = providerLink(display?.url)
  const brand = brandForUrl(url)
  return <div className="action-preview">
    {display ? <>
      <p className="action-title">{brand && <BrandIcon brand={brand} size={16} />} {display.title}</p>
      {display.lines.map((line, i) => <p className="action-line" key={i}>{line}</p>)}
      {url && <a className="action-open" href={url} target="_blank" rel="noreferrer">{brand && <BrandIcon brand={brand} size={14} />} Open ↗</a>}
      <AuditDetails summary={action.summary} />
    </> : <p className="action-legacy">{action.summary}</p>}
  </div>
}
