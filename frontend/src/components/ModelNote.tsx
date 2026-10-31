import { useModelInfo } from '../api/client'

export function ModelNote() {
  const { data } = useModelInfo()
  const test = data?.test
  const row = test?.full ?? test?.elo_only
  const base = test?.climatology
  return (
    <footer className="container note">
      Model {data?.version ?? ''}: built from Champions League results only (Elo ratings and
      recent form). Probabilities are estimates and can be overconfident for very lopsided
      matches, and the model has no special handling of draws.
      {row && base
        ? ` On held-out matches its log loss was ${row.log_loss.toFixed(3)}, against ${base.log_loss.toFixed(3)} for always guessing the base rates (lower is better).`
        : ''}
    </footer>
  )
}