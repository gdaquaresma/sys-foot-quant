"""Limites maximales de mise : garde-fou applique APRES tout calcul de
mise (Flat ou Kelly), quelle que soit sa provenance - dernier filet de
securite structurel contre une mise disproportionnee (erreur de calcul
en amont, bankroll anormalement basse, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StakeLimits:
    max_fraction_of_current_balance: float  # ex: 0.05 = jamais plus de 5% du solde courant
    max_absolute_stake: float | None = None  # plafond en unites monetaires, optionnel

    def __post_init__(self) -> None:
        if not (0.0 < self.max_fraction_of_current_balance <= 1.0):
            raise ValueError(
                "max_fraction_of_current_balance doit etre dans ]0, 1] "
                f"(recu {self.max_fraction_of_current_balance})."
            )
        if self.max_absolute_stake is not None and self.max_absolute_stake <= 0:
            raise ValueError(
                f"max_absolute_stake doit etre strictement positif si fourni "
                f"(recu {self.max_absolute_stake})."
            )


def apply_stake_limits(raw_stake: float, current_balance: float, limits: StakeLimits) -> float:
    """Ecrete ``raw_stake`` selon ``limits``. Ne renvoie jamais plus que le
    solde courant, quelles que soient les limites configurees."""
    if raw_stake < 0:
        raise ValueError(f"raw_stake ne peut pas etre negatif (recu {raw_stake}).")
    if current_balance <= 0:
        return 0.0

    capped = min(raw_stake, current_balance * limits.max_fraction_of_current_balance)
    if limits.max_absolute_stake is not None:
        capped = min(capped, limits.max_absolute_stake)
    return min(capped, current_balance)
