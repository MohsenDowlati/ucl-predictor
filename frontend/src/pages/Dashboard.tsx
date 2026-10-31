import { useState } from 'react'
import { useMatches } from '../api/client'
import type { Match } from '../api/types'
import { MatchCard } from '../components/MatchCard'
import { fmtDay } from '../format'

function groupByDay(matches: Match[]): [string, Match[]][] {
  const groups = new Map<string, Match[]>()
  for (const m of matches) {
    const key = fmtDay(m.kickoff)
    groups.set(key, [...(groups.get(key) ?? []), m])
  }
  return [...groups]
}

export default function Dashboard() {
  const upcoming = useMatches('upcoming', 200)
  const finished = useMatches('finished', 8)
  const [days, setDays] = useState(3)

  const groups = upcoming.data ? groupByDay(upcoming.data) : []

  return (
    <>
      <h1>Upcoming matches</h1>
      {upcoming.isPending && <p className="muted">Loading…</p>}
      {upcoming.isError && (
        <p className="error">Couldn't load matches ({upcoming.error.message}). Is the API running?</p>
      )}
      {upcoming.data && groups.length === 0 && <p className="muted">No upcoming matches.</p>}
      {groups.slice(0, days).map(([day, matches]) => (
        <section key={day}>
          <h2>{day}</h2>
          {matches.map((m) => (
            <MatchCard key={m.id} m={m} />
          ))}
        </section>
      ))}
      {groups.length > days && (
        <button onClick={() => setDays(days + 3)}>Show more days</button>
      )}

      <h2>Latest results</h2>
      {finished.isPending && <p className="muted">Loading…</p>}
      {finished.data?.map((m) => (
        <MatchCard key={m.id} m={m} />
      ))}
    </>
  )
}