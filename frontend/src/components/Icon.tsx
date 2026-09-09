import type { SVGProps } from 'react'

export type IconName = 'grid' | 'file' | 'briefcase' | 'send' | 'spark' | 'book' | 'mic' | 'chat' | 'chart' | 'chevron' | 'arrow' | 'refresh' | 'checkCircle' | 'check' | 'play'

const paths: Record<IconName, string> = {
  grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  file: 'M6 3h8l4 4v14H6zM14 3v5h5M9 13h6M9 17h5',
  briefcase: 'M4 7h16v13H4zM8 7V4h8v3M4 12h16',
  send: 'm3 11 18-8-8 18-2-8zM3 11l8 2',
  spark: 'm12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6z',
  book: 'M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 0 4 22zM4 5.5v16.5',
  mic: 'M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zM5 11a7 7 0 0 0 14 0M12 18v4',
  chat: 'M4 5h16v11H8l-4 4zM8 9h8M8 12h5',
  chart: 'M5 20V10M12 20V4M19 20v-7',
  chevron: 'm6 9 6 6 6-6',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  refresh: 'M20 11a8 8 0 1 0 1 4',
  checkCircle: 'M22 11.08V12a10 10 0 1 1-5.93-9.14',
  check: 'M20 6L9 17l-5-5',
  play: 'm8 5 11 7-11 7z',
}

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return <svg {...props} className={`icon ${props.className ?? ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
