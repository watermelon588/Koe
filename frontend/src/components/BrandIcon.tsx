import type { CSSProperties } from 'react'
import './brands.css'

const BRANDS = {
  github: { name: 'GitHub', file: 'github.png' },
  notion: { name: 'Notion', file: 'notion.svg' },
  google: { name: 'Google', file: 'google.png' },
  calendar: { name: 'Google Calendar', file: 'calendar.png' },
  meet: { name: 'Google Meet', file: 'meet.png' },
  sheets: { name: 'Google Sheets', file: 'sheets.png' },
  docs: { name: 'Google Docs', file: 'docs.png' },
  drive: { name: 'Google Drive', file: 'drive.png' },
  spotify: { name: 'Spotify', file: 'spotify.svg' },
  whatsapp: { name: 'WhatsApp', file: 'whatsapp.svg' },
  gemini: { name: 'Gemini', file: 'gemini.svg' },
} as const

export type Brand = keyof typeof BRANDS
export type BrandIconProps = { size?: number; className?: string; 'data-busy'?: boolean }

// Original provider artwork, stored locally; decorative when the adjacent text names the service.
export function BrandIcon({ brand, size = 24, className = '', 'data-busy': busy }: BrandIconProps & { brand: Brand }) {
  if (brand === 'spotify') size = Math.max(21, size) // Spotify's official minimum icon size
  return <img className={`brand-icon brand-icon--${brand} ${className}`} src={`/brands/${BRANDS[brand].file}`}
    width={size} height={size} style={{ '--brand-size': `${size}px` } as CSSProperties} alt="" aria-hidden="true" data-busy={busy || undefined} />
}

export const GoogleIcon = (props: BrandIconProps) => <BrandIcon brand="google" {...props} />
export const GitHubIcon = (props: BrandIconProps) => <BrandIcon brand="github" {...props} />
export const NotionIcon = (props: BrandIconProps) => <BrandIcon brand="notion" {...props} />
export const CalendarIcon = (props: BrandIconProps) => <BrandIcon brand="calendar" {...props} />
export const MeetIcon = (props: BrandIconProps) => <BrandIcon brand="meet" {...props} />
export const SheetsIcon = (props: BrandIconProps) => <BrandIcon brand="sheets" {...props} />
export const SpotifyIcon = (props: BrandIconProps) => <BrandIcon brand="spotify" {...props} />
export const GeminiIcon = (props: BrandIconProps) => <BrandIcon brand="gemini" {...props} />
