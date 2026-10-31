import { Link } from 'react-router-dom'
import type { Match } from '../api/types'
import { fmtTime, stageLabel, teamName } from '../format'
import { ProbabilityBar } from './ProbabilityBar'

export function MatchCard({ m }: { m: Match }) {
  const finished = m.status === 'FINISHED'
  return (
    <Link to={`/matches/${m.id}`} className="card">
      <div className="teams">
        <span className="team">{teamName(m.home)}</span>
        <span className="mid">
          {finished ? `${m.home_goals} – ${m.away_goals}` : fmtTime(m.kickoff)}
        </span>
        <span className="team away">{teamName(m.away)}</span>
      </div>
      {m.prediction ? (
        <ProbabilityBar p={m.prediction} />
      ) : (
        <div className="muted small">No prediction stored for this match</div>
      )}
      <div className="muted small">{stageLabel(m.stage)}</div>
    </Link>
  )
}