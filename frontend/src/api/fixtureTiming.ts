/**
 * Aide d'affichage PURE pour les informations temporelles d'une fixture
 * (`fixture_date`/`kickoff_local_naive`/`kickoff_utc`, voir `./types`) -
 * intégration frontend des fixtures futures 2026/27. Centralise la règle
 * produit UNIQUE (demande explicite : l'heure ne doit jamais bloquer
 * l'analyse d'une fixture Ligue 1 dont l'heure locale est publiée) :
 * une fixture est analysable si `kickoff_utc` est connu (confirmé) OU si
 * `kickoff_local_naive` est connu pour une compétition Ligue 1 (l'API
 * estime alors l'UTC par conversion CET/CEST - voir
 * `routes_prediction.py::_resolve_kickoff_utc`, INCHANGÉ ici, jamais
 * recalculé côté frontend). Seul un match SANS AUCUNE heure publiée
 * (état C) reste bloqué - aucune heure n'existe alors à convertir.
 * `AnalyzeMatch.tsx`/`MatchDetail.tsx`/`MatchExplorer.tsx` importent ces
 * fonctions plutôt que de ré-implémenter cette règle localement, pour
 * qu'elle ne puisse jamais diverger d'une page à l'autre.
 */
import type { MatchResponse } from './types'

const MONTHS_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

/** `fixture_date` ("YYYY-MM-DD", sans heure) -> date longue en français -
 * parsing MANUEL de la chaîne, jamais `new Date(fixtureDate)` : une date
 * SANS heure est interprétée par `Date` comme minuit UTC, ce qui peut
 * afficher la veille selon le fuseau horaire du navigateur - un décalage
 * que ce module interdit explicitement de laisser se produire. */
export function formatFixtureDate(fixtureDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(fixtureDate)
  if (!match) return fixtureDate
  const [, year, month, day] = match
  const monthName = MONTHS_FR[Number(month) - 1] ?? month
  return `${Number(day)} ${monthName} ${year}`
}

/** `kickoff_local_naive` ("YYYY-MM-DDTHH:mm:ss", SANS fuseau horaire) ->
 * "HH:mm" - extraction DIRECTE de la chaîne, jamais `new Date(...)` : ce
 * dernier réinterpréterait implicitement cette heure sans fuseau comme
 * l'heure locale du NAVIGATEUR, un calcul accidentel que ce module évite
 * en ne faisant jamais passer cette valeur par `Date`. */
export function formatLocalKickoffTime(kickoffLocalNaive: string): string {
  const match = /T(\d{2}):(\d{2})/.exec(kickoffLocalNaive)
  return match ? `${match[1]}:${match[2]}` : kickoffLocalNaive
}

/** Résultat de la règle produit UNIQUE : D (+ A, jamais observé
 * aujourd'hui) a `kickoff_utc` connu -> "utc_confirmed" ; B a l'heure
 * locale publiée mais pas l'UTC -> "local_only" ; C n'a aucune heure
 * publiée -> "unpublished". Dérivé UNIQUEMENT de la présence des champs
 * - jamais un `status` séparé qui pourrait se désynchroniser (même
 * principe que `future_fixture_catalog.py`, backend). */
export type FixtureTimingState = 'utc_confirmed' | 'local_only' | 'unpublished'

export function fixtureTimingState(match: MatchResponse): FixtureTimingState {
  if (match.kickoff_utc !== null) return 'utc_confirmed'
  if (match.kickoff_local_naive !== null) return 'local_only'
  return 'unpublished'
}

export type AnalysisAvailability = { available: true; estimated: boolean } | { available: false; reason: string }

/** Règle produit UNIQUE (voir docstring du module) : analysable si
 * `kickoff_utc` est connu (confirmé, `estimated: false`), OU si l'heure
 * locale est connue pour une fixture Ligue 1 (l'API estimera l'UTC par
 * conversion CET/CEST, `estimated: true` - le composant appelant doit
 * alors afficher cette estimation, jamais la masquer). Hors Ligue 1 avec
 * heure locale seule, ou aucune heure publiée du tout (état C) : analyse
 * indisponible, `reason` ne laisse JAMAIS entendre que le match sera
 * analysable plus tard à une heure précise, uniquement un fait présent. */
export function analysisAvailability(match: MatchResponse): AnalysisAvailability {
  if (match.kickoff_utc !== null) return { available: true, estimated: false }
  if (match.kickoff_local_naive !== null) {
    if (match.competition === 'ligue1') return { available: true, estimated: true }
    return {
      available: false,
      reason: 'Analyse indisponible : heure connue localement, mais estimation UTC non prise en charge pour cette compétition.',
    }
  }
  return {
    available: false,
    reason: 'Analyse indisponible : heure de coup d’envoi non publiée.',
  }
}
