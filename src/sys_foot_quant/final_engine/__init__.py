"""Moteur final (Phase B) - implementation du MVP decrit par
docs/final_engine_specification.md, lui-meme derive de la synthese
consolidee de la campagne experimentale E1->E16
(docs/research_synthesis_e1_e16.md, verdict RESEARCH PHASE CLOSED).

Pipeline en 6 niveaux, chacun dans son propre module, jamais un monolithe :

    Prediction (prediction.py)
        -> Calibration (calibration.py, E7/E8 - VALIDE SCIENTIFIQUEMENT)
        -> Pricing (pricing.py)
        -> Market comparison (market.py)
        -> Qualification (gates.py)
        -> Decision (decision.py)

``orchestrator.py`` assemble ces six niveaux sans jamais laisser l'un se
substituer a un autre (docs/final_engine_specification.md section 3).

RAPPEL NON NEGOCIABLE : ce moteur n'est PAS presente comme rentable, ni
predictif garanti, ni superieur au marche. C'est un systeme d'analyse
probabiliste et de qualification de prix, dont certaines proprietes sont
validees experimentalement (E7/E8) et d'autres restent des choix
operationnels explicitement marques comme tels (voir ``gates.py``).
"""
