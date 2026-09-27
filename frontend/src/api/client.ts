/**
 * Client API centralisé - point d'entrée UNIQUE pour tout appel HTTP vers
 * le backend sys-foot-quant. Aucune page ne doit appeler `fetch`
 * directement : toute nouvelle route consommée passe par une fonction
 * dédiée ici, qui retourne les données TELLES QUE l'API les fournit
 * (aucune transformation, aucun calcul, aucune valeur par défaut inventée
 * pour un champ absent).
 */
import type {
  ApiErrorDetail,
  MatchResponse,
  PerformanceResponse,
  ShadowObservation,
} from './types'

/** Toutes les requêtes passent par /api, proxifié par Vite en dev vers
 * l'API FastAPI locale (voir vite.config.ts) - jamais une URL absolue en
 * dur, pour rester agnostique de l'environnement de déploiement. */
const API_BASE = '/api'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(API_BASE + path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value)
    }
  }

  const response = await fetch(url.toString())

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as ApiErrorDetail | { detail: unknown }
      if (typeof body.detail === 'string') {
        detail = body.detail
      } else if (Array.isArray(body.detail)) {
        detail = body.detail.map((e) => (typeof e === 'object' && e && 'msg' in e ? String(e.msg) : String(e))).join('; ')
      }
    } catch {
      // corps non-JSON ou vide : conserve le detail generique ci-dessus,
      // jamais une exception masquee.
    }
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

export function getMatches(competition: string, season: string): Promise<MatchResponse[]> {
  return apiGet<MatchResponse[]>('/matches', { competition, season })
}

export function getMatch(matchId: string, competition: string, season: string): Promise<MatchResponse> {
  return apiGet<MatchResponse>(`/matches/${encodeURIComponent(matchId)}`, { competition, season })
}

export function getShadowJournal(): Promise<ShadowObservation[]> {
  return apiGet<ShadowObservation[]>('/shadow')
}

export function getShadowObservation(predictionId: string): Promise<ShadowObservation> {
  return apiGet<ShadowObservation>(`/shadow/${encodeURIComponent(predictionId)}`)
}

export function getPerformance(): Promise<PerformanceResponse> {
  return apiGet<PerformanceResponse>('/performance')
}
