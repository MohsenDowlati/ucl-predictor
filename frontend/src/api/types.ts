export interface TeamRef {
  id: number
  name: string
  short_name: string | null
}

export interface Probabilities {
  home: number
  draw: number
  away: number
  model_version: string
  created_at: string
}

export interface Match {
  id: number
  season: number
  kickoff: string
  stage: string | null
  status: string
  home: TeamRef
  away: TeamRef
  home_goals: number | null
  away_goals: number | null
  prediction: Probabilities | null
}

export interface MatchDetail extends Match {
  prediction_history: Probabilities[]
}

export interface Team {
  id: number
  name: string
  short_name: string | null
  elo: number | null
}

export interface EloPoint {
  date: string
  elo: number
  match_id: number
}

export interface TeamDetail extends Team {
  elo_history: EloPoint[]
  recent_matches: Match[]
  upcoming_matches: Match[]
}

export interface ScoreRow {
  log_loss: number
  brier: number
  accuracy: number
}

export interface ModelInfo {
  version: string
  test?: Record<string, ScoreRow>
}