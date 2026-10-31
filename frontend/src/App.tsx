import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { ModelNote } from './components/ModelNote'
import Dashboard from './pages/Dashboard'
import MatchDetail from './pages/MatchDetails'
import TeamPage from './pages/TeamPage'
import Teams from './pages/Teams'

export default function App() {
  return (
    <>
      <header className="site">
        <div className="container">
          <Link to="/" className="brand">UCL Predictor</Link>
          <nav>
            <NavLink to="/" end>Fixtures</NavLink>
            <NavLink to="/teams">Teams</NavLink>
          </nav>
        </div>
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/matches/:id" element={<MatchDetail />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/teams/:id" element={<TeamPage />} />
          <Route path="*" element={<p className="muted">Page not found.</p>} />
        </Routes>
      </main>
      <ModelNote />
    </>
  )
}