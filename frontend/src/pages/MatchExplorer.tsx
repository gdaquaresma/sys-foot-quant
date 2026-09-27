/**
 * Explorateur de matchs - STRUCTURE UNIQUEMENT pour cette phase (squelette
 * minimal, Phase UI-2-C). La sélection compétition/saison et l'appel à
 * GET /matches seront implémentés dans une phase ultérieure dédiée.
 * Aucune donnée fabriquée ici - la page indique explicitement qu'elle
 * n'est pas encore fonctionnelle plutôt que d'afficher un contenu
 * inventé.
 */
export function MatchExplorer() {
  return (
    <div className="page">
      <h1>Explorateur de matchs</h1>
      <p className="state state-empty">
        Non implémenté dans cette phase (squelette minimal UI-2-C). Consommera GET /matches (paramètres
        « competition »/« season » obligatoires - voir contrat API documenté).
      </p>
    </div>
  )
}
