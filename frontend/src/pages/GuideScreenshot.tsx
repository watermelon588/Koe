export function GuideScreenshot({ name, alt, caption, sample = true }: { name: string; alt: string; caption: string; sample?: boolean }) {
  return <figure className="guide-screenshot">
    <a href={`/guide/${name}.jpg`} target="_blank" rel="noopener" aria-label={`Open full-size screenshot: ${alt}`}>
      <img src={`/guide/${name}.jpg`} alt={alt} width="1280" height="900" loading="lazy" decoding="async" />
    </a>
    <figcaption><span>{sample ? 'EXAMPLE WORKSPACE · SAMPLE DATA' : 'THE KOE HOMEPAGE'}</span>{caption} <a href={`/guide/${name}.jpg`} target="_blank" rel="noopener">View full size ↗</a></figcaption>
  </figure>
}
