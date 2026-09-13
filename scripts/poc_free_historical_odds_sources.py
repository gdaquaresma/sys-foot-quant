"""POC/test isole - recherche de sources GRATUITES de cotes historiques
DEJA TELECHARGEABLES (GitHub/Hugging Face/Kaggle/autres depots publics)
permettant de construire un dataset PIT pour sys-foot-quant, apres
l'abandon de TheStatsAPI et d'OddsPortal (reseau bloque dans cette
session - voir ``research/thestatsapi_validation.md`` et
``research/oddsportal_validation.md``).

CE N'EST PAS UN MODULE DE PRODUCTION. Jamais importe par
``final_engine/``, ``scripts/predict_match.py``, R1/R2/R3/R4 ou
``shadow_mode/``. Aucune integration au moteur a ce stade.

CE QUI A ETE VERIFIE EMPIRIQUEMENT DANS CETTE SESSION (voir
``research/free_historical_odds_sources.md`` pour le detail complet) :

1. Hugging Face (``huggingface.co`` et tous ses sous-domaines CDN),
   Kaggle, Betfair (``historicdata.betfair.com``,
   ``developer.betfair.com``), aussportsbetting.com et
   sportsbookreviewsonline.com sont TOUS bloques par la meme politique
   d'egress obligatoire de cette session que TheStatsAPI/OddsPortal
   (403 policy denial au niveau du proxy, DNS/TCP fonctionnels par
   ailleurs quand teste). Aucune tentative de contournement.

2. GitHub (``github.com``, ``raw.githubusercontent.com``,
   ``codeload.github.com``, ``objects.githubusercontent.com``) EST
   accessible depuis cette session - contrairement a tous les autres
   fournisseurs testes precedemment. C'est la seule source de donnees
   externes reellement exploitable ici.

3. Recherche systematique (WebSearch + inspection reelle de fichiers
   via ``raw.githubusercontent.com``) : AUCUNE source GitHub trouvee ne
   contient un historique de MOUVEMENTS de cotes horodates (plusieurs
   observations par match) pour le football. Tout ce qui est reellement
   telechargeable est soit du code de scraper SANS donnees reelles
   commitees, soit un dataset a UNE seule ligne de cotes par match
   (ouverture ou fermeture, jamais les deux, jamais une serie).

4. Meilleur candidat concret TELECHARGE et LU depuis GitHub :
   ``eatpizzanot/soccer-dataset`` (echantillon de 1000 lignes reellement
   commite dans le depot, licence CC-BY-4.0). ``samples/odds.csv``
   contient EXACTEMENT 1 ligne par ``fixture_id`` (1000/1000), colonne
   ``bookmaker`` variee mais ``source`` toujours une cote de FERMETURE
   unique - Categorie C, confirme empiriquement.

5. Meilleur candidat sur le plan du SCHEMA (mais PAS telechargeable
   depuis cette session) : ``Lisandro79/BeatTheBookie`` (code source du
   papier academique arXiv:1710.02824, table ``odds_history_series``
   avec une colonne ``odds_datetime`` - un point par mise a jour de
   cote, jusqu'a 72 points par match d'apres ``src/unpack.py``, pour
   31 074 puis 82 786 matchs de football). Les fichiers de donnees
   reels ne sont PAS dans le depot GitHub : ils sont hebergent sur
   Dropbox/Google Drive/Kaggle - TOUS bloques par la meme politique
   d'egress (verifie avec l'URL Dropbox exacte du depot, voir
   ``attempt_download_beatthebookie_sample`` ci-dessous). Categorie B
   documentee (schema reel confirme par le code, pas par une simple
   promesse marketing) mais AUCUNE observation reelle obtenue.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EATPIZZANOT_SAMPLE_URL = "https://raw.githubusercontent.com/eatpizzanot/soccer-dataset/main/samples/odds.csv"

# URL Dropbox EXACTE citee dans le README reel de Lisandro79/BeatTheBookie
# (papier academique arXiv:1710.02824) pour le fichier "odds_series.zip" -
# le candidat au schema le plus proche de notre besoin PIT trouve dans
# cette recherche (voir docstring de module, point 5). Jamais heberge sur
# GitHub lui-meme - uniquement teste ici pour DOCUMENTER precisement le
# blocage, jamais pour le contourner.
BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL = "https://www.dropbox.com/s/gqp3m6o5zsd8v63/odds_series.zip?dl=1"

_REQUEST_TIMEOUT_SECONDS = 15.0


class DownloadBlockedError(RuntimeError):
    """Levee quand le telechargement echoue reellement - jamais confondue
    avec un resultat d'analyse sur des donnees deja obtenues."""


def download_text_file(url: str) -> str:
    """Telechargement reel, aucune donnee fabriquee en cas d'echec."""
    request = Request(url, headers={"Accept": "text/csv"})
    try:
        with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:  # nosec B310 - HTTPS uniquement
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise DownloadBlockedError(f"HTTP {exc.code} sur {url}.") from exc
    except URLError as exc:
        raise DownloadBlockedError(f"Connexion impossible vers {url} : {exc.reason}.") from exc


@dataclass(frozen=True)
class DownloadAttemptResult:
    url: str
    succeeded: bool
    detail: str


def attempt_download_beatthebookie_sample() -> DownloadAttemptResult:
    """Tentative reelle (jamais un contournement) de telechargement du
    dataset ``odds_series`` de BeatTheBookie (arXiv:1710.02824) depuis
    l'URL Dropbox EXACTE citee dans son README GitHub - le seul moyen
    d'obtenir des donnees reelles, puisqu'elles ne sont pas dans le
    depot GitHub lui-meme. Documente le resultat tel quel, succes ou
    echec, sans jamais fabriquer une donnee de repli."""
    try:
        request = Request(BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL, headers={"Accept": "application/zip"})
        with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS):  # nosec B310 - HTTPS uniquement
            return DownloadAttemptResult(
                url=BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL, succeeded=True, detail="Telechargement reussi."
            )
    except HTTPError as exc:
        return DownloadAttemptResult(
            url=BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL, succeeded=False, detail=f"HTTP {exc.code}."
        )
    except URLError as exc:
        return DownloadAttemptResult(
            url=BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL, succeeded=False, detail=f"Connexion impossible : {exc.reason}."
        )


# Depot original + chaque fork/reproduction identifie par recherche (WebSearch)
# comme une copie potentielle de BeatTheBookie - verifie ICI reellement, un par
# un, fichier par fichier, plutot que suppose absent. Aucun de ces depots n'a
# jamais commite les fichiers de donnees reels (voir
# research/free_historical_odds_sources.md, section "deuxieme mise a jour").
BEATTHEBOOKIE_CANDIDATE_REPOS: tuple[str, ...] = (
    "Lisandro79/BeatTheBookie",  # depot original
    "BobZombiE69/BeatTheBookie",  # fork
    "stv67/BeatThe-Bookie",  # fork
    "Lerbytech/BeatTheBookie",  # fork
    "zarklin/123",  # copie (nom generique, meme contenu README)
    "alannesta/BeatTheBookie",  # copie
)

# Chemins de fichiers de donnees plausibles d'apres le README/le code source
# reel (``src/unpack.py``, ``src/Figure1.m``) - jamais une simple supposition
# generique.
BEATTHEBOOKIE_CANDIDATE_DATA_PATHS: tuple[str, ...] = (
    "data/closing_odds.csv",
    "data/odds_series.csv",
    "data/odds_series_b.csv",
    "data/matches.csv",
    "closing_odds.csv",
    "odds_series.csv",
)


def check_beatthebookie_mirrors_for_real_data(
    repos: tuple[str, ...] = BEATTHEBOOKIE_CANDIDATE_REPOS,
    paths: tuple[str, ...] = BEATTHEBOOKIE_CANDIDATE_DATA_PATHS,
    branches: tuple[str, ...] = ("master", "main"),
) -> list[DownloadAttemptResult]:
    """Verifie REELLEMENT, un par un, si l'un des depots/forks/copies
    connus de BeatTheBookie a commite un fichier de donnees reel a l'un
    des chemins plausibles - jamais une conclusion tiree du seul README.
    Reproductible : peut etre relance depuis n'importe quel environnement
    avec acces reseau pour re-verifier si la situation a change."""
    results: list[DownloadAttemptResult] = []
    for repo in repos:
        for branch in branches:
            for path in paths:
                url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                request = Request(url, headers={"Accept": "text/csv"})
                try:
                    with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS):  # nosec B310 - HTTPS uniquement
                        results.append(DownloadAttemptResult(url=url, succeeded=True, detail="Fichier trouve."))
                except HTTPError as exc:
                    if exc.code != 404:
                        results.append(DownloadAttemptResult(url=url, succeeded=False, detail=f"HTTP {exc.code}."))
                except URLError:
                    pass  # branche/chemin absent - resultat attendu, pas une erreur a rapporter
    return results


@dataclass(frozen=True)
class OddsSampleAnalysis:
    """Resultat d'inspection REELLE d'un fichier de cotes - jamais deduit
    d'une description/README seule."""

    total_rows: int
    unique_match_keys: int
    max_rows_per_match: int
    rows_per_match_distribution: dict[int, int]
    bookmakers_observed: tuple[str, ...]
    sources_observed: tuple[str, ...]
    columns: tuple[str, ...]

    @property
    def is_single_snapshot_per_match(self) -> bool:
        """Vrai si chaque match n'a jamais plus d'une observation - donc
        structurellement une cote d'ouverture OU de fermeture, jamais une
        serie de mouvements exploitable pour le PIT."""
        return self.max_rows_per_match <= 1


def analyze_odds_csv(csv_text: str, match_key_column: str = "fixture_id") -> OddsSampleAnalysis:
    """Analyse REELLE (pas une supposition) de la granularite d'un fichier
    de cotes : combien d'observations existent reellement par match."""
    reader = csv.DictReader(csv_text.splitlines())
    rows = list(reader)
    if not rows:
        raise ValueError("Fichier CSV vide - impossible d'analyser la granularite.")

    columns = tuple(rows[0].keys())
    counts = Counter(row[match_key_column] for row in rows)
    distribution = dict(Counter(counts.values()))

    bookmaker_col = "bookmaker" if "bookmaker" in columns else None
    source_col = "source" if "source" in columns else None

    return OddsSampleAnalysis(
        total_rows=len(rows),
        unique_match_keys=len(counts),
        max_rows_per_match=max(counts.values()),
        rows_per_match_distribution=distribution,
        bookmakers_observed=tuple(sorted({row[bookmaker_col] for row in rows})) if bookmaker_col else (),
        sources_observed=tuple(sorted({row[source_col] for row in rows})) if source_col else (),
        columns=columns,
    )


def classify_pit_capability(analysis: OddsSampleAnalysis) -> str:
    """Classement explicite - jamais 'ACCEPTE'/'A' pour un fichier qui n'a
    jamais plus d'une observation par match, quelle que soit la
    description marketing du depot source."""
    if analysis.is_single_snapshot_per_match:
        return (
            "CATEGORIE C (backtest uniquement, PAS de PIT) - "
            f"{analysis.max_rows_per_match} observation(s) par match maximum, "
            "jamais une serie temporelle."
        )
    return (
        "CATEGORIE A/B CANDIDATE - plusieurs observations par match detectees, "
        "verification PIT complete requise (timestamps, fuseau horaire, ordre chronologique)."
    )


@dataclass(frozen=True)
class OddsObservation:
    match_key: str
    bookmaker: str
    market: str
    price: float
    timestamp: datetime


def select_last_observation_before(observations: list[OddsObservation], decision_time: datetime) -> OddsObservation | None:
    """Meme regle PIT stricte que partout ailleurs dans ce projet :
    ``timestamp < decision_time``, jamais ``<=``. Avec une seule
    observation par match (cas ``eatpizzanot/soccer-dataset``), cette
    fonction degenere : elle ne peut renvoyer que CETTE observation
    (si elle precede decision_time) ou rien - ce qui demontre
    concretement l'absence de granularite exploitable, plutot que de
    l'affirmer sans preuve."""
    eligible = [o for o in observations if o.timestamp < decision_time]
    if not eligible:
        return None
    return max(eligible, key=lambda o: o.timestamp)


def main() -> int:
    print(f"Telechargement reel depuis {EATPIZZANOT_SAMPLE_URL} ...")
    try:
        csv_text = download_text_file(EATPIZZANOT_SAMPLE_URL)
    except DownloadBlockedError as exc:
        print(f"ECHEC DE TELECHARGEMENT (aucune donnee fabriquee) : {exc}")
        return 1

    analysis = analyze_odds_csv(csv_text)
    print(f"Lignes totales      : {analysis.total_rows}")
    print(f"Matchs distincts    : {analysis.unique_match_keys}")
    print(f"Max obs. par match  : {analysis.max_rows_per_match}")
    print(f"Distribution        : {analysis.rows_per_match_distribution}")
    print(f"Bookmakers observes : {analysis.bookmakers_observed}")
    print(f"Sources observees   : {analysis.sources_observed}")
    print(f"Colonnes            : {analysis.columns}")
    print()
    print(f"Classement PIT : {classify_pit_capability(analysis)}")

    print()
    print("Tentative reelle de telechargement du candidat au meilleur schema")
    print(f"(BeatTheBookie odds_series, arXiv:1710.02824) depuis {BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL} ...")
    beatthebookie_attempt = attempt_download_beatthebookie_sample()
    if beatthebookie_attempt.succeeded:
        print("SUCCES INATTENDU - a analyser manuellement, aucune analyse automatique codee pour ce format.")
    else:
        print(f"ECHEC (aucune donnee fabriquee) : {beatthebookie_attempt.detail}")

    print()
    total_checks = len(BEATTHEBOOKIE_CANDIDATE_REPOS) * len(BEATTHEBOOKIE_CANDIDATE_DATA_PATHS) * 2
    print(f"Verification reelle de {len(BEATTHEBOOKIE_CANDIDATE_REPOS)} depots/forks/copies "
          f"BeatTheBookie x {len(BEATTHEBOOKIE_CANDIDATE_DATA_PATHS)} chemins plausibles "
          f"({total_checks} requetes) sur raw.githubusercontent.com ...")
    mirror_results = check_beatthebookie_mirrors_for_real_data()
    if not mirror_results:
        print("AUCUN fichier de donnees reel trouve dans aucun des depots/forks/copies verifies.")
    else:
        for r in mirror_results:
            print(f"  {r.url} -> {'TROUVE' if r.succeeded else 'ANOMALIE : ' + r.detail}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
