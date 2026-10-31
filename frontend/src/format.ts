import type { TeamRef } from './api/types'

export const pct = (x: number) => `${Math.round(x * 100)}%`

export const teamName = (t: TeamRef) => t.short_name ?? t.name

export const fmtDay = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })

export const fmtDateTime = (ms: number) =>
  new Date(ms).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })

export const fmtMonthYear = (ms: number) =>
  new Date(ms).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })

const STAGES: Record<string, string> = {
  GROUP_STAGE: 'Group stage',
  LEAGUE_STAGE: 'League phase',
  PLAYOFFS: 'Play-offs',
  LAST_16: 'Round of 16',
  QUARTER_FINALS: 'Quarter-finals',
  SEMI_FINALS: 'Semi-finals',
  FINAL: 'Final',
}

export const stageLabel = (s: string | null) => (s ? (STAGES[s] ?? s) : '')