/** Tests ciblés pour `StarredMatches.tsx` ("Mes paris") - page purement
 * dérivée de `starredMatches.ts` (localStorage), aucun appel réseau. */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { toggleStarredMatch } from '../api/starredMatches'
import { StarredMatches } from './StarredMatches'

beforeEach(() => {
  window.localStorage.clear()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <StarredMatches />
    </MemoryRouter>,
  )
}

describe('StarredMatches', () => {
  it('affiche un état vide quand aucun match n’est coché', () => {
    renderPage()
    expect(screen.getByText(/Aucun match coché pour l'instant/)).toBeInTheDocument()
  })

  it('affiche les matchs cochés, avec compétition/saison lisibles et un lien vers le détail', () => {
    toggleStarredMatch({ match_id: 'm1', competition: 'ligue1', season: '2026_27', home_team: 'Lens', away_team: 'Lyon' })
    renderPage()

    expect(screen.getByText('Ligue 1')).toBeInTheDocument()
    expect(screen.getByText('2026/27')).toBeInTheDocument()
    expect(screen.getByText('Lens – Lyon')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voir détail' })).toHaveAttribute('href', '/matches/ligue1/2026_27/m1')
  })

  it('retire un match de la liste au clic sur son étoile', () => {
    toggleStarredMatch({ match_id: 'm1', competition: 'ligue1', season: '2026_27', home_team: 'Lens', away_team: 'Lyon' })
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Retirer Lens – Lyon de mes paris' }))
    expect(screen.getByText(/Aucun match coché pour l'instant/)).toBeInTheDocument()
  })

  it('n’affiche jamais le vocabulaire d’une décision du moteur (BET/NO_BET) - ceci est une liste personnelle, pas une sortie du moteur', () => {
    toggleStarredMatch({ match_id: 'm1', competition: 'ligue1', season: '2026_27', home_team: 'Lens', away_team: 'Lyon' })
    renderPage()

    expect(screen.queryByText('BET')).not.toBeInTheDocument()
    expect(screen.queryByText('NO_BET')).not.toBeInTheDocument()
  })

  it('démarre avec "Mon pari"/"Résultat" non renseignés, jamais une valeur devinée', () => {
    toggleStarredMatch({ match_id: 'm1', competition: 'ligue1', season: '2026_27', home_team: 'Lens', away_team: 'Lyon' })
    renderPage()

    expect(screen.getByLabelText('Mon pari pour Lens – Lyon')).toHaveValue('')
    expect(screen.getByLabelText('Résultat de mon pari pour Lens – Lyon')).toHaveValue('')
  })

  it('enregistre le côté choisi et le résultat, et les conserve après un nouveau rendu', () => {
    toggleStarredMatch({ match_id: 'm1', competition: 'ligue1', season: '2026_27', home_team: 'Lens', away_team: 'Lyon' })
    const { unmount } = renderPage()

    fireEvent.change(screen.getByLabelText('Mon pari pour Lens – Lyon'), { target: { value: 'Under' } })
    fireEvent.change(screen.getByLabelText('Résultat de mon pari pour Lens – Lyon'), { target: { value: 'won' } })
    expect(screen.getByLabelText('Mon pari pour Lens – Lyon')).toHaveValue('Under')
    expect(screen.getByLabelText('Résultat de mon pari pour Lens – Lyon')).toHaveValue('won')

    // Persisté réellement (localStorage), pas seulement un état React en mémoire.
    unmount()
    renderPage()
    expect(screen.getByLabelText('Mon pari pour Lens – Lyon')).toHaveValue('Under')
    expect(screen.getByLabelText('Résultat de mon pari pour Lens – Lyon')).toHaveValue('won')
  })
})
