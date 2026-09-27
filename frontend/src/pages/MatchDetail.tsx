/**
 * Analyse détaillée d'un match - STRUCTURE UNIQUEMENT pour cette phase.
 *
 * Limite connue et documentée (Phase UI-2-C, à trancher avec le
 * responsable produit) : le contrat API actuel (GET /matches/{match_id})
 * n'expose QUE les métadonnées du catalogue (équipes, date, joué/non
 * joué) - aucune route de prédiction n'existe. Cette page ne pourra donc
 * jamais afficher une décision BET/NO_BET pour ce match tant qu'une telle
 * route n'est pas ajoutée à l'API (hors périmètre de cette phase, et
 * explicitement interdit de fabriquer côté frontend).
 */
import { useParams } from 'react-router-dom'

export function MatchDetail() {
  const { competition, season, matchId } = useParams()

  return (
    <div className="page">
      <h1>Détail du match</h1>
      <p className="state state-empty">
        Non implémenté dans cette phase (squelette minimal UI-2-C). Consommera GET /matches/{'{match_id}'} pour{' '}
        {competition}/{season}/{matchId}. Aucune analyse de décision ne pourra être affichée tant qu'aucune route de
        prédiction n'existe côté API.
      </p>
    </div>
  )
}
