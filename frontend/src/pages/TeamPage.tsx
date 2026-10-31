import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useParams } from 'react-router-dom'
import { useTeam } from '../api/client'
import { MatchCard } from '../components/MatchCard'
import { fmtMonthYear } from '../format'

export default function TeamPage() {
  const { id } = useParams()
  const q = useTeam(Number(id))

  if (q.isPending) return <p className="muted">Loading…</p>
  if (q.isError) return <p className="error">Couldn't load this team ({q.error.message}).</p>

  const t = q.data
  const points = t.elo_history.map((p) => ({ t: Date.parse(p.date), elo: p.elo }))

  return (
    <>
      <h1>{t.name}</h1>
      <p className="muted">
        Current Elo rating: <strong>{t.elo === null ? '–' : Math.round(t.elo)}</strong>
      </p>

      <h2>Rating over time</h2>
      {points.length < 2 ? (
        <p className="muted">Not enough matches to draw a rating history.</p>
      ) : (
        <div className="card">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={points}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
              <XAxis
                dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']}
                tickFormatter={fmtMonthYear} minTickGap={40}
              />
              <YAxis domain={['auto', 'auto']} />
              <Tooltip
                labelFormatter={(x) => fmtMonthYear(Number(x))}
                formatter={(v) => Math.round(Number(v))}
              />
              <Line dataKey="elo" name="Elo" stroke="#2563eb" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {t.upcoming_matches.length > 0 && <h2>Upcoming</h2>}
      {t.upcoming_matches.map((m) => <MatchCard key={m.id} m={m} />)}

      <h2>Recent results</h2>
      {t.recent_matches.length === 0 && <p className="muted">No matches yet.</p>}
      {t.recent_matches.map((m) => <MatchCard key={m.id} m={m} />)}
    </>
  )
}