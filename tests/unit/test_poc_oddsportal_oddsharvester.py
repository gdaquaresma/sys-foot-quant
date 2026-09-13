"""Tests unitaires du POC OddsPortal/OddsHarvester
(``scripts/poc_oddsportal_oddsharvester.py``).

Aucun de ces tests n'appelle le reseau. La demonstration du bug d'annee
d'OddsHarvester 0.12.0 utilise une entree HTML SYNTHETIQUE construite pour
respecter exactement les selecteurs CSS reels de son code source (voir
docstring du module teste) - elle sert a tester le CODE tiers reproduit
ici, jamais a fabriquer une conclusion sur des donnees OddsPortal
reelles (qui restent NON VERIFIEES, reseau bloque)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "poc_oddsportal_oddsharvester.py"


def _load_poc():
    spec = importlib.util.spec_from_file_location("poc_oddsportal_oddsharvester_for_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def poc():
    return _load_poc()


# --- 1. Reproduction du parsing reel d'OddsHarvester 0.12.0 -----------------
# Fixture HTML synthetique respectant exactement les selecteurs CSS reels
# (div.flex.flex-row.gap-3 > div.flex.flex-col.gap-1 pour les colonnes
# timestamps/valeurs, div.mt-2.gap-1 pour l'ouverture) - jamais une
# capture reelle d'OddsPortal (bloque).

_SYNTHETIC_MODAL_HTML = """
<div>
  <div class="flex flex-row gap-3">
    <div class="flex flex-col gap-1">
      <div class="font-normal">08 Nov, 09:00</div>
      <div class="font-normal">10 Nov, 14:00</div>
    </div>
    <div class="flex flex-col gap-1">
      <div class="font-bold">1.85</div>
      <div class="font-bold">1.73</div>
    </div>
  </div>
  <div class="mt-2 gap-1">
    <div class="flex gap-1">
      <div>05 Nov, 12:00</div>
      <div class="font-bold">1.90</div>
    </div>
  </div>
</div>
"""


def test_vendored_parser_extracts_history_points_and_opening(poc) -> None:
    result = poc.parse_odds_history_modal_oddsharvester_v0_12_0(_SYNTHETIC_MODAL_HTML)
    assert len(result["odds_history"]) == 2
    assert result["odds_history"][0]["odds"] == 1.85
    assert result["odds_history"][1]["odds"] == 1.73
    assert result["opening_odds"]["odds"] == 1.90


def test_vendored_parser_reproduces_the_real_year_bug(poc) -> None:
    """Demonstration reelle (pas une hypothese) du bug d'OddsHarvester
    0.12.0 : le texte affiche par OddsPortal ("08 Nov, 09:00") ne contient
    aucune annee - le code complete avec l'annee COURANTE (celle du
    scraping), jamais celle du match reel. Si ce match datait en realite
    de 2024 mais qu'on rejoue ce parseur aujourd'hui, l'annee produite est
    fausse."""
    result = poc.parse_odds_history_modal_oddsharvester_v0_12_0(_SYNTHETIC_MODAL_HTML)
    produced_year = datetime.fromisoformat(result["odds_history"][0]["timestamp"]).year
    assert produced_year == datetime.now(timezone.utc).year
    # Le vrai match de reference (Chelsea vs Arsenal) a eu lieu en 2024 -
    # si l'annee courante n'est pas 2024, la sortie brute est deja fausse
    # sans aucune correction, ce que ce test rend visible plutot que de
    # l'affirmer sans preuve.
    if datetime.now(timezone.utc).year != 2024:
        assert produced_year != 2024


def test_vendored_parser_produces_naive_timestamps(poc) -> None:
    """Deuxieme defaut reel : aucun fuseau horaire n'est jamais attache."""
    result = poc.parse_odds_history_modal_oddsharvester_v0_12_0(_SYNTHETIC_MODAL_HTML)
    parsed = datetime.fromisoformat(result["odds_history"][0]["timestamp"])
    assert parsed.tzinfo is None


def test_vendored_parser_handles_missing_columns_gracefully(poc) -> None:
    result = poc.parse_odds_history_modal_oddsharvester_v0_12_0("<div>no matching structure</div>")
    assert result["odds_history"] == []
    assert result["opening_odds"] is None


# --- 2. correct_oddsharvester_year : correctif cote appelant ----------------


def test_correct_oddsharvester_year_recovers_the_real_year(poc) -> None:
    naive = datetime(2026, 11, 8, 9, 0, 0)  # annee fausse produite par le parseur ci-dessus
    reference_date = date(2024, 11, 10)  # kickoff reel de Chelsea vs Arsenal
    corrected = poc.correct_oddsharvester_year(naive, reference_date)
    assert corrected.year == 2024
    assert (corrected.month, corrected.day) == (11, 8)


def test_correct_oddsharvester_year_handles_december_january_wraparound(poc) -> None:
    """Un mouvement de cote le 30 decembre pour un match le 2 janvier de
    l'annee suivante doit resoudre vers l'annee du mouvement, pas celle
    du kickoff."""
    naive = datetime(2099, 12, 30, 23, 0, 0)  # annee fausse
    reference_date = date(2025, 1, 2)
    corrected = poc.correct_oddsharvester_year(naive, reference_date, max_drift_days=5)
    assert corrected.year == 2024
    assert (corrected.month, corrected.day) == (12, 30)


def test_correct_oddsharvester_year_refuses_when_ambiguous_or_impossible(poc) -> None:
    """Un mouvement a plus de max_drift_days de toute annee candidate ne
    doit jamais etre devine silencieusement."""
    naive = datetime(2099, 6, 15, 10, 0, 0)
    reference_date = date(2024, 11, 10)  # ~5 mois d'ecart, hors tolerance
    with pytest.raises(ValueError, match="Correction d'annee"):
        poc.correct_oddsharvester_year(naive, reference_date, max_drift_days=5)


# --- 3. attach_assumed_timezone ---------------------------------------------


def test_attach_assumed_timezone_requires_explicit_tz(poc) -> None:
    naive = datetime(2024, 11, 8, 9, 0, 0)
    aware = poc.attach_assumed_timezone(naive, timezone.utc)
    assert aware.tzinfo is timezone.utc


def test_attach_assumed_timezone_refuses_to_overwrite_aware_timestamp(poc) -> None:
    already_aware = datetime(2024, 11, 8, 9, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="deja timezone-aware"):
        poc.attach_assumed_timezone(already_aware, timezone.utc)


# --- 4. select_last_snapshot_before (regle PIT) -----------------------------


def test_select_last_snapshot_before_returns_most_recent_eligible(poc) -> None:
    early = poc.OddsMovement(bookmaker="Pinnacle", market="over_under_2_5", outcome="over", odds=1.85, timestamp=datetime(2024, 11, 8, 9, 0, 0, tzinfo=timezone.utc))
    late = poc.OddsMovement(bookmaker="Pinnacle", market="over_under_2_5", outcome="over", odds=1.73, timestamp=datetime(2024, 11, 10, 14, 0, 0, tzinfo=timezone.utc))
    decision_time = datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert poc.select_last_snapshot_before([early, late], decision_time) is late


def test_select_last_snapshot_before_excludes_snapshot_at_exact_decision_time(poc) -> None:
    at_decision_time = poc.OddsMovement(bookmaker="Pinnacle", market="over_under_2_5", outcome="over", odds=1.73, timestamp=datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc))
    decision_time = datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert poc.select_last_snapshot_before([at_decision_time], decision_time) is None


def test_select_last_snapshot_before_excludes_future_snapshot(poc) -> None:
    future = poc.OddsMovement(bookmaker="Pinnacle", market="over_under_2_5", outcome="over", odds=1.73, timestamp=datetime(2024, 11, 10, 17, 0, 0, tzinfo=timezone.utc))
    decision_time = datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert poc.select_last_snapshot_before([future], decision_time) is None


def test_select_last_snapshot_before_returns_none_for_empty_input(poc) -> None:
    assert poc.select_last_snapshot_before([], datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)) is None


# --- 5. Diagnostic reseau reel (verifie sa structure, pas son resultat) -----


def test_check_oddsportal_network_access_returns_structured_result(poc) -> None:
    """Test reellement le reseau (comme le script lui-meme) - le resultat
    depend de l'environnement d'execution, jamais fabrique. On verifie
    uniquement que la structure retournee est coherente et que
    ``blocked_at_proxy_only`` reflete bien DNS+TCP ok / HTTPS refuse quand
    c'est le cas observe (signature exacte d'un refus de politique)."""
    result = poc.check_oddsportal_network_access()
    assert isinstance(result.dns_resolved, bool)
    assert isinstance(result.raw_tcp_connect_ok, bool)
    assert isinstance(result.https_via_proxy_ok, bool)
    if result.dns_resolved and result.raw_tcp_connect_ok and not result.https_via_proxy_ok:
        assert result.blocked_at_proxy_only is True


# --- 6. format_checkpoint_table : jamais de donnee fabriquee ----------------


def test_format_checkpoint_table_never_fabricates_a_value(poc) -> None:
    table = poc.format_checkpoint_table(list(poc.REFERENCE_MATCHES), "test bloque")
    assert "NON VERIFIE" in table
    assert "test bloque" in table
    # Aucune valeur de cote (float plausible du type 1.7x/2.1x) ne doit
    # apparaitre dans un rapport qui n'a rien observe reellement.
    import re

    assert not re.search(r"\b1\.\d{2}\b", table)


# --- 7. main() : chemin reseau bloque, sans reseau fabrique -----------------


def test_main_returns_1_and_reports_all_checkpoints_when_blocked(poc, monkeypatch, capsys) -> None:
    blocked_result = poc.NetworkCheckResult(
        host="www.oddsportal.com",
        dns_resolved=True,
        dns_detail="ok",
        raw_tcp_connect_ok=True,
        raw_tcp_detail="ok",
        https_via_proxy_ok=False,
        https_via_proxy_detail="403 Forbidden",
    )
    monkeypatch.setattr(poc, "check_oddsportal_network_access", lambda: blocked_result)
    exit_code = poc.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ACCES BLOQUE" in captured.out
    assert captured.out.count("NON VERIFIE") == len(poc.REFERENCE_MATCHES) * 7
