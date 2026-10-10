/**
 * "Mes paris" - liste de matchs que l'UTILISATEUR a personnellement cochés
 * pour les repérer (ex. un pari qu'il a placé ailleurs, sur un site de
 * paris réel) - PURE annotation côté présentation, aucun lien avec le
 * moteur : n'affecte jamais `run_prediction`/`final_engine`, ne crée
 * jamais d'observation dans le journal Shadow Mode
 * (`research/shadow_mode/predictions.jsonl`, INCHANGÉ, jamais touché par
 * ce module), et n'exécute aucun pari réel - c'est un pense-bête personnel,
 * pas une décision du système.
 *
 * Stockage : `localStorage`, propre à CE navigateur - ne survit pas à un
 * autre appareil/navigateur, peut être vidé par l'utilisateur ou son
 * navigateur à tout moment. Choix délibéré : il n'existe aujourd'hui
 * aucune route API d'écriture pour ce besoin (l'API reste documentée
 * "lecture seule", voir `api/app.py`), et cette donnée est une pure
 * commodité personnelle, pas une donnée scientifique à faire persister de
 * façon durable/partagée.
 */
export type MyPick = 'Over' | 'Under'
export type MyResult = 'won' | 'lost'

export interface StarredMatch {
  match_id: string
  competition: string
  season: string
  home_team: string
  away_team: string
  /** Horodatage ISO de l'ajout - affichage seul, jamais utilisé pour un calcul. */
  starred_at: string
  /** Côté (Over/Under 2.5) que L'UTILISATEUR dit avoir choisi pour son pari
   * réel - saisie manuelle uniquement, jamais déduite du pronostic du
   * modèle (voir AnalyzeMatch.tsx) : l'utilisateur peut parfaitement avoir
   * parié différemment de ce que le modèle favorise. `null` tant que non
   * renseigné. */
  my_pick: MyPick | null
  /** Résultat de CE pari réel, tel que déclaré par l'utilisateur -
   * jamais déduit automatiquement d'un règlement Shadow Mode (ce sont deux
   * choses distinctes : un pari réel de l'utilisateur, et une observation
   * du moteur). `null` tant que non renseigné ("en attente"). */
  result: MyResult | null
}

const STORAGE_KEY = 'sys-foot-quant:starred-matches'
const CHANGE_EVENT = 'sys-foot-quant:starred-matches-changed'

// Cache en mémoire, invalidé par comparaison avec la DERNIÈRE chaîne brute
// lue (pas par un événement) - requis par `useSyncExternalStore` (voir
// `useStarredMatches.ts`) : son `getSnapshot` doit retourner la MÊME
// référence tant que le contenu réel n'a pas changé, sinon React le
// détecte comme "changé à chaque rendu" et boucle. Comparer la chaîne
// brute (plutôt que de ne jamais relire) reste correct même si
// `localStorage` est modifié directement (ex. un autre onglet, ou un
// `localStorage.clear()`), sans dépendre de l'événement `storage` (qui ne
// se déclenche jamais dans l'onglet qui a fait le changement lui-même).
let lastRaw: string | null = null
let cache: StarredMatch[] = []

function readAll(): StarredMatch[] {
  let raw: string | null
  try {
    raw = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    raw = null
  }
  if (raw === lastRaw) return cache
  lastRaw = raw
  try {
    const parsed = raw ? JSON.parse(raw) : []
    cache = Array.isArray(parsed) ? parsed : []
  } catch {
    // Contenu corrompu - jamais un plantage, simplement aucun match étoilé.
    cache = []
  }
  return cache
}

function writeAll(matches: StarredMatch[]): void {
  cache = matches
  try {
    lastRaw = JSON.stringify(matches)
    window.localStorage.setItem(STORAGE_KEY, lastRaw)
  } catch {
    // Écriture impossible (quota, navigation privée stricte) - l'étoile ne
    // persistera pas au rechargement, mais l'application continue de
    // fonctionner pour la session en cours (le cache mémoire reste à jour).
  }
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

export function listStarredMatches(): StarredMatch[] {
  return readAll()
}

export function isMatchStarred(matchId: string): boolean {
  return readAll().some((m) => m.match_id === matchId)
}

/** Ajoute ou retire `match` de la liste - jamais de doublon (déduplique
 * sur `match_id`, déjà unique par construction côté catalogue). Un nouvel
 * ajout démarre toujours avec `my_pick`/`result` à `null` - jamais une
 * valeur devinée. */
export function toggleStarredMatch(match: Omit<StarredMatch, 'starred_at' | 'my_pick' | 'result'>): void {
  const current = readAll()
  const exists = current.some((m) => m.match_id === match.match_id)
  writeAll(
    exists
      ? current.filter((m) => m.match_id !== match.match_id)
      : [...current, { ...match, starred_at: new Date().toISOString(), my_pick: null, result: null }],
  )
}

/** Met à jour `my_pick`/`result` pour un match DÉJÀ étoilé - saisie
 * manuelle exclusivement, jamais un recalcul. N'a aucun effet si
 * `matchId` n'est plus dans la liste (ex. retiré entre-temps dans un autre
 * onglet) - refus silencieux plutôt qu'une exception, cohérent avec le
 * reste de ce module qui ne lève jamais pour une donnée de confort. */
export function updateStarredMatch(matchId: string, updates: Partial<Pick<StarredMatch, 'my_pick' | 'result'>>): void {
  const current = readAll()
  if (!current.some((m) => m.match_id === matchId)) return
  writeAll(current.map((m) => (m.match_id === matchId ? { ...m, ...updates } : m)))
}

/** S'abonne aux changements (ajout/retrait, y compris depuis un autre
 * onglet via l'événement natif `storage`) - utilisé par `useStarredMatches`
 * pour garder plusieurs composants synchronisés sans prop drilling. */
export function subscribeStarredMatches(callback: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}
