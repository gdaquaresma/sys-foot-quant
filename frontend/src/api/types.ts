/**
 * Types reflétant EXACTEMENT le contrat de l'API sys-foot-quant
 * (src/sys_foot_quant/api/*.py, Phase UI-2-B) - documentés à partir du
 * code source et de réponses HTTP réelles, jamais supposés. Ne JAMAIS
 * ajouter un champ ici qui ne provient pas d'une réponse réelle de l'API.
 */

// --- GET /matches, GET /matches/{match_id} ----------------------------------

export interface MatchResponse {
  match_id: string
  competition: string
  season: string
  /** ISO 8601 avec suffixe Z (UTC) - sérialisation Pydantic. */
  kickoff_utc: string
  home_team: string
  away_team: string
  is_played: boolean
}

// --- GET /shadow, GET /shadow/{prediction_id} -------------------------------
//
// Forme volontairement large (le backend ne modélise pas ces vues en
// Pydantic strict non plus - voir schemas.py - pour ne jamais perdre un
// champ non anticipé). Les sous-objets `models`/`market_comparison`
// utilisent `Record<string, unknown>` plutôt qu'une interface figée, pour
// la même raison : ne jamais laisser le frontend supposer une forme que
// l'API ne garantit pas contractuellement.

export interface ShadowGate {
  name: string
  failure_code: string | null
  reason: string
}

export interface ShadowSettlement {
  settled_at: string
  home_goals_actual: number
  away_goals_actual: number
  total_goals_actual: number
  market_result_over_2_5: string
  pnl_theoretical: number | null
}

export interface ShadowObservation {
  prediction_id: string
  /** Chaine ISO SANS suffixe Z (naive) - different du format /matches. */
  recorded_at: string
  decision_time: string
  competition: string
  season: string
  home_team: string
  away_team: string
  kickoff_utc: string
  decision_offset_hours: number
  market_odds_over_2_5: number | null
  market_odds_under_2_5: number | null
  odds_bookmaker: string | null
  odds_market: string | null
  odds_line: number | null
  primary_model: string
  models: Record<string, unknown>
  market_comparison: Record<string, unknown> | null
  calibration_status_over_2_5: string | null
  discrimination_status: string
  data_quality: string[]
  triggered_gates: ShadowGate[]
  /** "BET" n'est structurellement jamais produit par le moteur actuel
   * (edge_threshold_gate toujours declenche) - reste une valeur legitime
   * du type, jamais a exclure du typage. */
  decision: 'BET' | 'NO_BET'
  decision_reason: string[]
  engine_version: string
  status: 'PENDING' | 'SETTLED'
  settlement: ShadowSettlement | null
}

// --- GET /performance --------------------------------------------------------

export interface PerformanceModelEvaluation {
  n: number
  brier: number | null
  log_loss: number | null
  calibration_bins: Record<string, unknown>[] | null
}

export interface PerformanceBetting {
  n_bet: number
  message?: string
  win_rate?: number
  total_pnl_theoretical?: number
  roi_theoretical?: number
  clv?: number | null
  clv_unavailable_reason?: string
}

export interface PerformanceResponse {
  n_total: number
  n_pending: number
  n_settled: number
  decision_distribution: Record<string, number>
  models: Record<string, PerformanceModelEvaluation>
  betting: PerformanceBetting
  calibration_min_observations: number
}

// --- GET /matches/{match_id}/prediction -------------------------------------
//
// Reflète EXACTEMENT dataclasses.asdict(MatchDecisionOutput)
// (final_engine/types.py, INCHANGE) tel que sérialisé par
// routes_prediction.py - vérifié sur une réponse réelle (match Brest–PSG,
// id 31975). `observed_value`/`threshold` sur un gate n'ont pas de forme
// fixe (nombre, chaîne, liste, objet ou null selon le gate) : `unknown`,
// jamais une forme supposée. Les clés numériques (seuils de buts, ex.
// "2.5") sont sérialisées en chaînes par le JSON - `Record<string, number>`.

export interface ModelPrediction {
  model: string
  lam: number
  mu: number
  rho: number | null
  n_train_matches: number
}

export interface CalibratedGoalDistribution {
  model: string
  scale_c: number | null
  n_calibration_used: number
  goal_distribution: number[] | null
  probabilities: Record<string, number> | null
}

export interface PricingResult {
  fair_price: Record<string, number>
}

export interface MarketComparisonResult {
  market_odds: Record<string, number>
  market_implied_probability_raw: Record<string, number>
  market_implied_probability_normalized: Record<string, number>
  market_overround: number
  raw_edge: Record<string, number>
  price_edge: Record<string, number>
}

export interface PredictionGateResult {
  name: string
  triggered: boolean
  reason: string
  metric: string
  observed_value: unknown
  threshold: unknown
  failure_code: string | null
}

export interface QualificationResult {
  calibration_status: Record<string, string>
  discrimination_status: string
  data_quality: string[]
  scientific_gates: PredictionGateResult[]
  operational_gates: PredictionGateResult[]
}

export interface PredictionDecisionResult {
  /** "BET" n'est structurellement jamais produit par le moteur actuel
   * (edge_threshold_gate toujours declenche) - reste une valeur legitime
   * du type, jamais a exclure du typage. */
  decision: 'BET' | 'NO_BET'
  decision_reason: string[]
}

export interface MatchDecisionOutput {
  /** Identifiant interne généré par le moteur (composite
   * compétition/saison/équipes/coup d'envoi) - DIFFÉRENT du `match_id` de
   * catalogue utilisé par l'URL et `GET /matches/{match_id}`. */
  match_id: string
  /** Chaine ISO SANS suffixe Z (naive), comme /shadow. */
  timestamp_decision: string
  competition: string
  season: string
  primary_model: string
  models: Record<string, ModelPrediction | null>
  calibration: Record<string, CalibratedGoalDistribution>
  pricing: Record<string, PricingResult | null>
  market: MarketComparisonResult | null
  qualification: QualificationResult
  decision: PredictionDecisionResult
  engine_version: string
  parameters_snapshot: Record<string, unknown>
}

// --- Erreurs -------------------------------------------------------------

/** Forme d'erreur pour 400/404 (gestionnaire d'erreurs global de l'API). */
export interface ApiErrorDetail {
  detail: string
}

/** Forme d'erreur 422 (validation FastAPI standard). */
export interface ApiValidationErrorDetail {
  detail: Array<{ type: string; loc: (string | number)[]; msg: string }>
}
