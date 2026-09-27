/**
 * États réutilisables (loading/empty/error) - AUCUN de ces composants ne
 * fabrique de donnée : ils ne font qu'afficher un message explicite.
 */

export function LoadingState({ label = 'Chargement...' }: { label?: string }) {
  return <p className="state state-loading">{label}</p>
}

export function ErrorState({ message }: { message: string }) {
  return <p className="state state-error">Erreur : {message}</p>
}

export function EmptyState({ message }: { message: string }) {
  return <p className="state state-empty">{message}</p>
}

export function DecisionBadge({ decision }: { decision: 'BET' | 'NO_BET' }) {
  return <span className={`badge badge-${decision.toLowerCase()}`}>{decision}</span>
}

export function StatusBadge({ status }: { status: 'PENDING' | 'SETTLED' }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status}</span>
}
