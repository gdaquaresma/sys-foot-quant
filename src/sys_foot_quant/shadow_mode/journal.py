"""Journal Shadow Mode V1 : observe les decisions de
``final_engine.orchestrator.run_match_decision`` (INCHANGE) sur des matchs
REELS, hors echantillon, sans jamais reentrainer, recalibrer ni modifier le
moteur en fonction des resultats observes.

Principe non negociable (separation temporelle) :

    informations disponibles avant le match -> predict_match.py -> decision
    ENREGISTREE (immuable) -> match joue -> resultat reel ajoute APRES COUP
    -> evaluation.

Mecanisme d'immutabilite (append-only, deux TYPES de ligne dans le meme
fichier JSONL, jamais une reecriture d'une ligne deja ecrite) :

- une ligne ``record_type="prediction"`` par observation, ecrite UNE SEULE
  FOIS par ``record_prediction`` - contient exclusivement des champs
  connaissables AVANT le match (identifiants, cotes utilisees, sorties du
  moteur). Cette ligne n'est plus jamais reecrite ni modifiee, par
  construction (aucune fonction de ce module n'ouvre le fichier en mode
  ecriture destructive pour une ligne ``prediction`` existante) ;
- une ligne ``record_type="settlement"`` par observation REGLEE, ecrite UNE
  SEULE FOIS par ``settle_prediction``, apres coup - contient exclusivement
  le resultat reel. Ne contient et ne peut jamais contenir aucun champ
  pre-match (nouvelle ligne distincte, jamais un merge en ecriture).

``load_journal``/``find_prediction`` fabriquent une VUE fusionnee en
lecture seule (jamais persistee) pour l'affichage/l'evaluation - la
fusion ne modifie jamais le fichier sur disque.

Aucune nouvelle logique de modelisation/calibration : ce module lit
uniquement les champs deja produits par ``MatchDecisionOutput``
(``final_engine.types``, INCHANGE)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from sys_foot_quant.calibration_engine.reliability import reliability_bins
from sys_foot_quant.final_engine.types import MatchDecisionOutput

DEFAULT_JOURNAL_PATH = Path("research/shadow_mode/predictions.jsonl")

STATUS_PENDING = "PENDING"
STATUS_SETTLED = "SETTLED"

_RECORD_TYPE_PREDICTION = "prediction"
_RECORD_TYPE_SETTLEMENT = "settlement"

_MODELS = ("poisson_simple", "dixon_coles", "xg_model")

# Seuil d'AFFICHAGE (pas un critere de validation scientifique - ceux-la
# restent E2/E3/E7/E8/E11/E14, INCHANGES) sous lequel une courbe de
# calibration par tranche n'est pas montree dans le rapport Shadow Mode,
# faute d'echantillon suffisant pour etre lisible.
MIN_OBSERVATIONS_FOR_CALIBRATION_DISPLAY = 20

# Rappel structurel (docs/final_engine_user_guide.md) : final_engine ne
# compare jamais qu'une cote D'OUVERTURE au marche, jamais de cloture
# (E16) - ce journal n'enregistre donc jamais de cote de cloture, et le
# CLV ne peut structurellement pas etre calcule dans ce protocole.
CLV_UNAVAILABLE_REASON = (
    "aucune cote de cloture dans ce protocole - jamais utilisee par final_engine (E16)."
)


class ShadowModeError(ValueError):
    """Refus explicite (observation introuvable, deja reglee, journal
    absent/invalide) - jamais un comportement silencieux."""


def compute_prediction_id(
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    decision_offset_hours: float,
    market_odds_over_2_5: float | None,
    market_odds_under_2_5: float | None,
) -> str:
    """Identifiant deterministe d'une observation : LA MEME combinaison
    d'entrees produit TOUJOURS le meme ``prediction_id`` (reproductibilite,
    R4) - permet la deduplication d'une prediction accidentellement
    relancee. Ne depend d'aucune heure d'enregistrement ni d'aucun champ
    calcule par le moteur, uniquement des parametres fournis par
    l'appelant (les memes que ``predict_match.run_prediction``)."""
    payload = "|".join(
        [
            competition,
            season,
            home_team,
            away_team,
            kickoff_utc.isoformat(),
            f"{decision_offset_hours:.6f}",
            "" if market_odds_over_2_5 is None else f"{market_odds_over_2_5:.6f}",
            "" if market_odds_under_2_5 is None else f"{market_odds_under_2_5:.6f}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _model_summary(output: MatchDecisionOutput) -> dict:
    summary = {}
    for model in _MODELS:
        pred = output.models.get(model)
        calib = output.calibration.get(model)
        pricing = output.pricing.get(model)
        probabilities = calib.probabilities if calib and calib.probabilities else None
        summary[model] = {
            "lambda": pred.lam if pred else None,
            "mu": pred.mu if pred else None,
            "rho": pred.rho if pred else None,
            "n_train_matches": pred.n_train_matches if pred else None,
            "scale_c": calib.scale_c if calib else None,
            "n_calibration_used": calib.n_calibration_used if calib else None,
            # Cles en chaine (les seuils O/U sont des float cote moteur) -
            # explicite plutot que de dependre de la coercion JSON implicite.
            "probabilities": {str(t): p for t, p in probabilities.items()} if probabilities else None,
            "fair_price_over_2_5": (pricing.fair_price.get(2.5) if pricing else None),
        }
    return summary


def _triggered_gates(output: MatchDecisionOutput) -> list[dict]:
    all_gates = output.qualification.scientific_gates + output.qualification.operational_gates
    return [
        {"name": g.name, "failure_code": g.failure_code, "reason": g.reason} for g in all_gates if g.triggered
    ]


def _build_prediction_fields(
    output: MatchDecisionOutput,
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    decision_offset_hours: float,
    market_odds_over_2_5: float | None,
    market_odds_under_2_5: float | None,
) -> dict:
    """Champs pre-match IMMUABLES d'une observation - construits par simple
    LECTURE d'un ``output`` DEJA produit par ``run_match_decision``
    (INCHANGE) : aucun recalcul, aucune nouvelle logique."""
    market = output.market
    return {
        "prediction_id": compute_prediction_id(
            competition, season, home_team, away_team, kickoff_utc, decision_offset_hours,
            market_odds_over_2_5, market_odds_under_2_5,
        ),
        # Metadonnee d'audit uniquement (quand l'observation a ete
        # journalisee) - jamais utilisee par le moteur, par
        # ``compute_prediction_id`` ni par l'evaluation.
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "decision_time": output.timestamp_decision.isoformat(),
        "competition": competition,
        "season": season,
        "home_team": home_team,
        "away_team": away_team,
        "kickoff_utc": kickoff_utc.isoformat(),
        "decision_offset_hours": decision_offset_hours,
        "market_odds_over_2_5": market_odds_over_2_5,
        "market_odds_under_2_5": market_odds_under_2_5,
        "primary_model": output.primary_model,
        "models": _model_summary(output),
        "market_comparison": None
        if market is None
        else {
            "implied_prob_over_2_5": market.market_implied_probability_normalized.get("Over"),
            "implied_prob_under_2_5": market.market_implied_probability_normalized.get("Under"),
            "overround": market.market_overround,
            "raw_edge_over_2_5": market.raw_edge.get("Over"),
            "ev_over_2_5": market.price_edge.get("Over"),
        },
        "calibration_status_over_2_5": output.qualification.calibration_status.get(2.5),
        "discrimination_status": output.qualification.discrimination_status,
        "data_quality": output.qualification.data_quality,
        "triggered_gates": _triggered_gates(output),
        "decision": output.decision.decision,
        "decision_reason": output.decision.decision_reason,
        "engine_version": output.engine_version,
    }


def _append_line(journal_path: Path, line: dict) -> None:
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with open(journal_path, "a") as f:
        f.write(json.dumps(line) + "\n")


def _read_raw_lines(journal_path: Path) -> list[dict]:
    if not journal_path.exists():
        return []
    lines = []
    with open(journal_path) as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if raw_line:
                lines.append(json.loads(raw_line))
    return lines


def _resolve_view(prediction_line: dict, settlement_line: dict | None) -> dict:
    fields = {k: v for k, v in prediction_line.items() if k != "record_type"}
    if settlement_line is None:
        return {**fields, "status": STATUS_PENDING, "settlement": None}
    settlement = {k: v for k, v in settlement_line.items() if k not in ("record_type", "prediction_id")}
    return {**fields, "status": STATUS_SETTLED, "settlement": settlement}


def load_journal(journal_path: Path = DEFAULT_JOURNAL_PATH) -> list[dict]:
    """Vue fusionnee, en LECTURE SEULE, de toutes les observations - une
    entree par ``prediction_id``, avec ``status``/``settlement`` resolus a
    partir des lignes ``settlement`` correspondantes si elles existent.
    Ne modifie jamais le fichier."""
    raw = _read_raw_lines(journal_path)
    predictions = {r["prediction_id"]: r for r in raw if r.get("record_type") == _RECORD_TYPE_PREDICTION}
    settlements = {r["prediction_id"]: r for r in raw if r.get("record_type") == _RECORD_TYPE_SETTLEMENT}
    return [_resolve_view(pred, settlements.get(pid)) for pid, pred in predictions.items()]


def find_prediction(journal_path: Path, prediction_id: str) -> dict | None:
    for view in load_journal(journal_path):
        if view["prediction_id"] == prediction_id:
            return view
    return None


def record_prediction(
    output: MatchDecisionOutput,
    competition: str,
    season: str,
    home_team: str,
    away_team: str,
    kickoff_utc: datetime,
    decision_offset_hours: float,
    market_odds_over_2_5: float | None,
    market_odds_under_2_5: float | None,
    journal_path: Path = DEFAULT_JOURNAL_PATH,
) -> tuple[dict, bool]:
    """Enregistre une observation pre-match dans le journal Shadow Mode -
    APPEND-ONLY, jamais une reecriture. Deduplique explicitement sur
    ``prediction_id`` (deterministe) : si une observation IDENTIQUE existe
    deja, ne l'ecrit PAS une deuxieme fois - retourne l'observation
    existante et ``already_existed=True`` plutot que de creer
    silencieusement un doublon.

    Retourne ``(vue_resolue, already_existed)``."""
    fields = _build_prediction_fields(
        output, competition, season, home_team, away_team, kickoff_utc, decision_offset_hours,
        market_odds_over_2_5, market_odds_under_2_5,
    )
    prediction_id = fields["prediction_id"]
    existing = find_prediction(journal_path, prediction_id)
    if existing is not None:
        return existing, True

    _append_line(journal_path, {"record_type": _RECORD_TYPE_PREDICTION, **fields})
    return _resolve_view({"record_type": _RECORD_TYPE_PREDICTION, **fields}, None), False


def settle_prediction(
    prediction_id: str,
    home_goals: int,
    away_goals: int,
    journal_path: Path = DEFAULT_JOURNAL_PATH,
) -> dict:
    """Ajoute le resultat REEL d'une observation DEJA enregistree -
    operation POST-MATCH UNIQUEMENT, qui n'ecrit qu'une NOUVELLE ligne
    ``settlement`` (jamais une reecriture de la ligne ``prediction``
    existante - aucun champ pre-match ne peut donc etre altere par cette
    fonction, par construction). Leve explicitement si l'observation
    n'existe pas ou est deja reglee - jamais un ecrasement silencieux
    d'un settlement existant."""
    prediction_view = find_prediction(journal_path, prediction_id)
    if prediction_view is None:
        raise ShadowModeError(f"Aucune observation avec prediction_id={prediction_id!r} dans {journal_path}.")
    if prediction_view["status"] == STATUS_SETTLED:
        raise ShadowModeError(f"Prediction {prediction_id!r} deja reglee - jamais un second settlement silencieux.")

    total_goals_actual = home_goals + away_goals
    pnl_theoretical = None
    if prediction_view["decision"] == "BET":
        # Convention flat 1 unite deja etablie
        # (scripts/run_stage6_economic_b365_ev.py) - jamais une nouvelle
        # regle de mise. edge_threshold_gate (final_engine/gates.py) ne
        # controle que market.raw_edge["Over"] : un BET de ce moteur ne
        # peut structurellement designer qu'un pari sur Over 2.5 -
        # structurellement inatteignable tant que min_edge_threshold
        # reste None (voir docs/final_engine_user_guide.md).
        over_odds = prediction_view["market_odds_over_2_5"]
        if over_odds is None:
            raise ShadowModeError(
                f"Prediction {prediction_id!r} marquee BET sans cote Over 2.5 enregistree - "
                "invariant du moteur viole, refus de calculer un P&L."
            )
        pnl_theoretical = (over_odds - 1.0) if total_goals_actual > 2.5 else -1.0

    settlement_fields = {
        "settled_at": datetime.now(timezone.utc).isoformat(),
        "home_goals_actual": home_goals,
        "away_goals_actual": away_goals,
        "total_goals_actual": total_goals_actual,
        "market_result_over_2_5": "Over" if total_goals_actual > 2.5 else "Under",
        "pnl_theoretical": pnl_theoretical,
    }
    _append_line(
        journal_path,
        {"record_type": _RECORD_TYPE_SETTLEMENT, "prediction_id": prediction_id, **settlement_fields},
    )
    return {**prediction_view, "status": STATUS_SETTLED, "settlement": settlement_fields}


def _binary_brier_and_logloss(probs: np.ndarray, outcomes: np.ndarray) -> tuple[float, float]:
    """Formule standard (identique a celle deja utilisee par
    ``scripts/run_stage8_diagnostic_total_goals_over_under.py.
    _binary_brier_and_logloss``, jamais une nouvelle metrique) - dupliquee
    ici car celle-la est privee a un script de recherche isole (meme
    convention de duplication minimale que le reste du projet)."""
    eps = 1e-12
    brier = float(np.mean((probs - outcomes) ** 2))
    p_clipped = np.clip(probs, eps, 1 - eps)
    logloss = float(-np.mean(outcomes * np.log(p_clipped) + (1 - outcomes) * np.log(1 - p_clipped)))
    return brier, logloss


def evaluate_shadow(journal_path: Path = DEFAULT_JOURNAL_PATH) -> dict:
    """Evalue les observations REGLEES du journal - lecture seule, ne
    modifie jamais le journal ni le moteur. N'invente JAMAIS un BET :
    si aucune observation reglee n'a ``decision == "BET"``
    (comportement attendu tant que ``min_edge_threshold`` reste ``None``),
    la section ``betting`` le signale explicitement plutot que de
    fabriquer un echantillon."""
    records = load_journal(journal_path)
    settled = [r for r in records if r["status"] == STATUS_SETTLED]

    decision_distribution: dict[str, int] = {}
    for r in records:
        decision_distribution[r["decision"]] = decision_distribution.get(r["decision"], 0) + 1

    models_eval: dict[str, dict] = {}
    for model in _MODELS:
        probs: list[float] = []
        outcomes: list[float] = []
        for r in settled:
            proba_dict = r["models"][model]["probabilities"]
            if proba_dict is None or "2.5" not in proba_dict:
                continue
            probs.append(proba_dict["2.5"])
            outcomes.append(1.0 if r["settlement"]["total_goals_actual"] > 2.5 else 0.0)

        if not probs:
            models_eval[model] = {"n": 0, "brier": None, "log_loss": None, "calibration_bins": None}
            continue

        probs_arr = np.array(probs)
        outcomes_arr = np.array(outcomes)
        brier, logloss = _binary_brier_and_logloss(probs_arr, outcomes_arr)
        bins = None
        if len(probs) >= MIN_OBSERVATIONS_FOR_CALIBRATION_DISPLAY:
            bins = reliability_bins(probs_arr, outcomes_arr, n_bins=5).to_dict("records")
        models_eval[model] = {"n": len(probs), "brier": brier, "log_loss": logloss, "calibration_bins": bins}

    bet_records = [r for r in settled if r["decision"] == "BET"]
    if not bet_records:
        betting_eval = {
            "n_bet": 0,
            "message": "0 BET — echantillon insuffisant pour evaluer une strategie de mise.",
        }
    else:
        pnls = [r["settlement"]["pnl_theoretical"] for r in bet_records]
        wins = sum(1 for pnl in pnls if pnl is not None and pnl > 0)
        betting_eval = {
            "n_bet": len(bet_records),
            "win_rate": wins / len(bet_records),
            "total_pnl_theoretical": sum(pnls),
            "roi_theoretical": sum(pnls) / len(bet_records),
            "clv": None,
            "clv_unavailable_reason": CLV_UNAVAILABLE_REASON,
        }

    return {
        "n_total": len(records),
        "n_pending": len(records) - len(settled),
        "n_settled": len(settled),
        "decision_distribution": decision_distribution,
        "models": models_eval,
        "betting": betting_eval,
        "calibration_min_observations": MIN_OBSERVATIONS_FOR_CALIBRATION_DISPLAY,
    }
