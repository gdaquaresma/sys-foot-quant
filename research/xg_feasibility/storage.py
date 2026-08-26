"""Serialisation d'une extraction datee (protocole B3, priorite 2).

Le champ ``collected_at`` est ce qui rend la mesure de revision possible :
sans une date de collecte explicite et fiable pour CHAQUE extraction, il
serait impossible de distinguer "cette valeur a change entre les deux
extractions" de "je ne sais pas quand ces valeurs ont ete lues". Fonctions
PURES (lecture/ecriture disque uniquement, aucun acces reseau)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from research.xg_feasibility.understat_source import MatchXGRecord

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExtractionFile:
    collected_at: datetime
    league: str
    season: str
    records: list[MatchXGRecord]


def save_extraction(
    records: list[MatchXGRecord],
    out_path: str | Path,
    league: str,
    season: str,
    collected_at: datetime | None = None,
) -> None:
    """Ecrit l'extraction en JSON. ``collected_at`` par defaut = maintenant
    (UTC) - ne jamais le laisser implicite/absent : c'est la piece
    d'information centrale du protocole de mesure."""
    ts = collected_at or datetime.now(timezone.utc)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "collected_at": ts.isoformat(),
        "league": league,
        "season": season,
        "records": [
            {**asdict(r), "kickoff_utc": r.kickoff_utc.isoformat()} for r in records
        ],
    }
    Path(out_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_extraction(path: str | Path) -> ExtractionFile:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(
            f"Version de schema inattendue dans {path} : {raw.get('schema_version')!r} "
            f"(attendu {_SCHEMA_VERSION}) - format d'extraction incompatible."
        )
    records = [
        MatchXGRecord(
            match_id=r["match_id"],
            league=r["league"],
            season=r["season"],
            kickoff_utc=datetime.fromisoformat(r["kickoff_utc"]),
            home_team=r["home_team"],
            away_team=r["away_team"],
            home_goals=r["home_goals"],
            away_goals=r["away_goals"],
            home_xg=r["home_xg"],
            away_xg=r["away_xg"],
        )
        for r in raw["records"]
    ]
    return ExtractionFile(
        collected_at=datetime.fromisoformat(raw["collected_at"]),
        league=raw["league"],
        season=raw["season"],
        records=records,
    )
