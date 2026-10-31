import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTeams } from '../api/client'

export default function Teams() {
  const [activeOnly, setActiveOnly] = useState(true)
  const q = useTeams(activeOnly)

  return (
    <>
      <h1>Team ratings</h1>
      <label className="small">
        <input
          type="checkbox" checked={activeOnly}
          onChange={(e) => setActiveOnly(e.target.checked)}
        />{' '}
        Only clubs from the last two seasons
      </label>
      {q.isPending && <p className="muted">Loading…</p>}
      {q.isError && <p className="error">Couldn't load teams ({q.error.message}).</p>}
      {q.data && (
        <table>
          <thead>
            <tr><th>#</th><th>Team</th><th className="num">Elo</th></tr>
          </thead>
          <tbody>
            {q.data.map((t, i) => (
              <tr key={t.id}>
                <td>{i + 1}</td>
                <td><Link to={`/teams/${t.id}`}>{t.name}</Link></td>
                <td className="num">{t.elo === null ? '–' : Math.round(t.elo)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}