import type { Probabilities } from '../api/types'
import { pct } from '../format'

export function ProbabilityBar({ p, large = false }: { p: Probabilities; large?: boolean }) {
  const parts = [
    { key: 'home', value: p.home },
    { key: 'draw', value: p.draw },
    { key: 'away', value: p.away },
  ]
  return (
    <div
      className={`probbar${large ? ' large' : ''}`}
      role="img"
      aria-label={`Home win ${pct(p.home)}, draw ${pct(p.draw)}, away win ${pct(p.away)}`}
    >
      {parts.map(({ key, value }) => (
        <div key={key} className={`seg ${key}`} style={{ flexGrow: value }}>
          {value >= 0.1 ? pct(value) : ''}
        </div>
      ))}
    </div>
  )
}