import { useQuery } from '@tanstack/react-query'
import type { Match, MatchDetail, ModelInfo, Team, TeamDetail } from './types'

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export const useMatches = (status: 'upcoming' | 'finished', limit: number) =>
  useQuery({
    queryKey: ['matches', status, limit],
    queryFn: () => getJSON<Match[]>(`/matches?status=${status}&limit=${limit}`),
    refetchInterval: 60_000,
  })

export const useMatch = (id: number) =>
  useQuery({
    queryKey: ['match', id],
    queryFn: () => getJSON<MatchDetail>(`/matches/${id}`),
  })

export const useTeams = (activeOnly: boolean) =>
  useQuery({
    queryKey: ['teams', activeOnly],
    queryFn: () => getJSON<Team[]>(`/teams?active_only=${activeOnly}`),
  })

export const useTeam = (id: number) =>
  useQuery({
    queryKey: ['team', id],
    queryFn: () => getJSON<TeamDetail>(`/teams/${id}`),
  })

export const useModelInfo = () =>
  useQuery({
    queryKey: ['model-info'],
    queryFn: () => getJSON<ModelInfo>('/model/info'),
    retry: false,
  })