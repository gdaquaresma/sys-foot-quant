import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'

// Sans `test.globals` dans vite.config.ts (choix deliberer pour garder les
// imports explicites - voir chaque fichier de test), le nettoyage
// automatique du DOM entre les tests de @testing-library/react ne
// s'enclenche pas tout seul : l'enregistrer explicitement ici evite toute
// contamination du DOM entre tests d'un meme fichier.
afterEach(() => {
  cleanup()
})
