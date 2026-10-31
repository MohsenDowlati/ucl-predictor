import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Link, useParams } from 'react-router-dom'
import { useMatch } from '../api/client'
import { ProbabilityBar } from '../components/ProbabilityBar'
import { fmtDateTime, fmtDay, fmtTime, pct, stageLabel } from '../format'

export default function MatchDetail() {
  const { id } = useParams()
  const q = useMatch(Number(id))

  if (q.isPending) return <p className="muted">Loading…</p>
  if (q.isError) return <p className="error">Couldn't load this match ({q.error.message}).</p>

  const m = q.data
  const finished = m.status === 'FINISHED'
  const history = m.prediction_history.map((p) => ({
    t: Date.parse(p.created_at),
    home: p.home * 100,
    draw: p.draw * 100,
    away: p.away * 100,
  }))

  return (
    <>
      <p className="muted small">
        {stageLabel(m.stage)} · {fmtDay(m.kickoff)}, {fmtTime(m.kickoff)}
      </p>
      <h1 className="matchtitle">
        <Link to={`/teams/${m.home.id}`}>{m.home.name}</Link>
        <span className="mid">{finished ? `${m.home_goals} – ${m.away_goals}` : 'v'}</span>
        <Link to={`/teams/${m.away.id}`}>{m.away.name}</Link>
      </h1>
      {finished && <p className="muted small">Score after 90 minutes.</p>}

      <h2>{finished ? 'Last pre-match prediction' : 'Win probabilities'}</h2>
      {m.prediction ? (
        <>
          <ProbabilityBar p={m.prediction} large />
          <p className="legend">
            <span className="dot home" /> {m.home.name} {pct(m.prediction.home)}
            <span className="dot draw" /> Draw {pct(m.prediction.draw)}
            <span className="dot away" /> {m.away.name} {pct(m.prediction.away)}
          </p>
        </>
      ) : (
        <p className="muted">No prediction stored for this match.</p>
      )}

      <h2>How the odds have moved</h2>
      {history.length < 2 ? (
        <p className="muted">
          Only one prediction so far. A point is added each time new results change the odds
          for this match.
        </p>
      ) : (
        <div className="card">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
              <XAxis
                dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']}
                tickFormatter={fmtDateTime} minTickGap={40}
              />
              <YAxis domain={[0, 100]} unit="%" />
              <Tooltip
                labelFormatter={(t) => fmtDateTime(Number(t))}
                formatter={(v) => `${Number(v).toFixed(1)}%`}
              />
              <Legend />
              <Line dataKey="home" name="Home win" stroke="#2563eb" dot />
              <Line dataKey="draw" name="Draw" stroke="#64748b" dot />
              <Line dataKey="away" name="Away win" stroke="#c2410c" dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  )
}