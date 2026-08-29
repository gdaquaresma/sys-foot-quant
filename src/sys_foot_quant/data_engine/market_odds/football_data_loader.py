"""Import des cotes reelles Football-Data.co.uk, marche 1X2 (Bet365, Bet&Win,
Pinnacle, William Hill, Ladbrokes) ET Over/Under 2.5 (Bet365 ET Pinnacle) -
etape 4, phase economique (docs/decisions/0006-football-data-point-in-time.md) ;
extension Over/Under 2.5 B365 - E5 ; extension multi-bookmaker 1X2 (BW, PS) - E9 ;
extension multi-bookmaker 1X2 (WH, LB) ET Over/Under 2.5 Pinnacle (colonne
``P``) - E13 ; extension COTES DE CLOTURE (B365/BW/PS 1X2, B365/P Over/Under
2.5, WH/LB 1X2 optionnelles) - E16, meme decision, section "Extension future".

Perimetre strictement respecte : seules les colonnes ``Date``, ``Time``,
``HomeTeam``, ``AwayTeam``, ``FTHG``, ``FTAG``, ``FTR``, ``B365H/D/A``,
``BWH/D/A``, ``PSH/D/A``, ``B365>2.5``, ``B365<2.5``, ``P>2.5``, ``P<2.5``,
et DEPUIS E16 leurs equivalents de CLOTURE ``B365CH/D/A``, ``BWCH/D/A``,
``PSCH/D/A``, ``B365C>2.5``, ``B365C<2.5``, ``PC>2.5``, ``PC<2.5``
(TOUJOURS presentes, _ALLOWED_COLUMNS, echec explicite si absentes) et
``WHH/D/A``, ``LBH/D/A``, ``WHCH/D/A``, ``LBCH/D/A`` (colonnes OPTIONNELLES
PAR FICHIER, _OPTIONAL_COLUMNS - lues seulement si presentes dans le
fichier, jamais une erreur si absentes) sont lues. AUCUN agregat de marche
(``Max``/``Avg`` - deja exclus par l'ADR 0006, decision non revisitee en
E13/E16), AUCUN bookmaker au-dela de ceux listes (notamment PAS ``BFE`` -
nature d'exchange non clarifiee, voir E9/E13) n'est touche - meme si
present dans le fichier source. Aucune colonne de cloture Over/Under pour
BW/WH/LB n'existe dans les fichiers sources (seuls B365 et P publient ce
marche, cf. constat E13 ci-dessous) - perimetre volontairement limite a ce
qui existe reellement.

CONSTAT EMPIRIQUE (E13, inspection directe des six fichiers, jamais
suppose) : ``WHH/D/A`` (William Hill) n'existe que dans les fichiers
2024/25 ; ``LBH/D/A`` (Ladbrokes) n'existe que dans les fichiers 2025/26 -
Football-Data change le nom de ce "5e" bookmaker suivi d'une saison a
l'autre. ``WH`` et ``LB`` sont donc des bookmakers DIFFERENTS, JAMAIS
fusionnes sous un meme nom, et jamais simultanement presents pour un
meme match. D'ou le mecanisme ``_OPTIONAL_COLUMNS`` : contrairement a
``_ALLOWED_COLUMNS`` (colonnes garanties presentes dans les six fichiers,
echec explicite si absentes), une colonne optionnelle absente DU FICHIER
(pas seulement de la ligne) ne leve jamais d'erreur - le champ vaut
``None`` pour tous les matchs de ce fichier, exactement comme un
bookmaker absent d'un match individuel.

SECOND CONSTAT EMPIRIQUE (E13, inspection DIRECTE de l'en-tete brut,
corrigeant une hypothese implicite non verifiee des etapes precedentes -
E9/E10/E11/E12 avaient suppose B365 seul sur l'Over/Under) : les six
fichiers contiennent aussi ``P>2.5``/``P<2.5`` - Pinnacle publie une cote
Over/Under 2.5, sous le prefixe ``P`` (distinct du prefixe ``PS`` utilise
pour son 1X2 - convention historique propre a Football-Data, deux
prefixes pour le meme bookmaker selon le marche). Couverture constatee :
quasi-complete (99.2-99.5%) sur les fichiers 2024/25, degradee (~45-50%
manquant) sur les fichiers 2025/26 - EXACTEMENT le meme profil de
degradation par saison que ``PSH/D/A`` (1X2), ce qui corrobore qu'il
s'agit du meme bookmaker (Pinnacle). L'Over/Under 2.5 dispose donc
reellement de DEUX bookmakers nommes (B365, P) - pas un seul - la
dispersion/le consensus/l'arbitrage inter-bookmakers y redeviennent
evaluables (voir E13, section X de docs/research_framework.md).

``B365>2.5``/``B365<2.5`` et ``B365H/D/A`` sont completes a 100% sur les
six fichiers reels. ``BW``/``PS``/``WH``/``LB``/``P`` (O/U) sont chacun
PARTIELLEMENT complets (couverture variable par saison - constate, jamais
suppose - un bookmaker absent sur un match donne est simplement absent du
snapshot multi-bookmaker, jamais invente ni impute) : aucun O/U 2.5
n'existe pour BW/WH/LB dans les fichiers sources (colonnes absentes) -
seuls B365 et P (Pinnacle) portent ce marche - perimetre volontairement
limite a ce qui existe reellement.

RESERVE CRITIQUE (E16, non negociable - voir docs/research_framework.md
section AA) : les colonnes de cloture sont lues UNIQUEMENT pour une etude
RETROSPECTIVE du mouvement de marche (ouverture -> cloture) - elles NE
SONT JAMAIS disponibles au moment de la decision (`decision_time` =
kickoff - `DECISION_OFFSET_HOURS`, meme regle que partout ailleurs) et NE
DOIVENT JAMAIS etre utilisees comme feature d'une prediction censee etre
disponible a l'ouverture. Aucun script anterieur (E1-E15) ne lit ces
champs ; leur ajout ici n'affecte donc AUCUN resultat deja publie.

EXTENSION PHASE F (docs/next_signal_strategy.md, docs/sot_incremental_information_experiment.md) :
ajout de ``HST``/``AST`` (tirs cadres domicile/exterieur) a
``_ALLOWED_COLUMNS`` - COUVERTURE VERIFIEE (jamais supposee) : 0 valeur
manquante sur les six fichiers reels (2132 lignes), ``HST<=HS`` et
``AST<=AS`` toujours vrai. Ce sont des STATISTIQUES DE MATCH, connues
seulement APRES le coup d'envoi (meme moment de publication que
``FTHG``/``FTAG`` dans la meme ligne source) - JAMAIS un feature du match
qu'elles decrivent lui-meme, uniquement exploitables comme entree
HISTORIQUE (moyenne glissante d'un match anterieur) d'un futur match,
exactement comme ``goals_knowledge_time`` (``real_data_walk_forward.py``,
kickoff+2h) le fait deja pour les buts reels - aucun nouveau delai de
connaissance n'est invente ici. Aucune autre colonne de statistique de
match (``HS``/``AS``/``HC``/``AC``/``HF``/``AF``/``HY``/``AY``/``HR``/
``AR``) n'est lue - perimetre volontairement limite a l'hypothese
prioritaire (tirs cadres), une seule source d'information nouvelle a la
fois (voir protocole Phase F).

EXTENSION PHASE G (docs/bfe_incremental_information_experiment.md) : audit
DIRECT des colonnes Betfair (jamais lues avant Phase G, `BFE` etait
explicitement exclu depuis E9/E13 - "nature d'exchange non clarifiee").
Inspection de l'en-tete brut des six fichiers reels a revele DEUX
instruments Betfair DISTINCTS, jamais un seul :
- ``BFH``/``BFD``/``BFA`` (fichiers 2024/25) renomme ``BFDH``/``BFDD``/
  ``BFDA`` (fichiers 2025/26) - EXACTEMENT le meme phenomene de
  renommage inter-saison deja documente pour WH/LB (E13) : UN SEUL
  bookmaker, deux noms de colonne selon la saison. Overround moyen
  empirique 1.045-1.060 sur les six fichiers - PROFIL IDENTIQUE a B365
  (1.055-1.056) - signature d'un bookmaker a marge fixe classique
  ("Betfair Sportsbook"). 1X2 UNIQUEMENT (aucune colonne Over/Under ni
  handicap asiatique pour cet instrument, dans aucun des six fichiers).
  **NON LU** - redondant par construction avec les bookmakers a marge
  deja exclus comme non-informatifs (BW/PS/WH/LB, E9/E13), et hors
  perimetre de l'hypothese Phase G (une seule variable nouvelle : BFE).
- ``BFEH``/``BFED``/``BFEA`` (1X2), ``BFE>2.5``/``BFE<2.5`` (Over/Under
  2.5) - CONSTANT sur les six fichiers (jamais renomme). Overround moyen
  empirique 1.006-1.013 - PRES DE 1.0, tres inferieur au profil de tout
  bookmaker du corpus - signature attendue d'un prix d'echange ("best
  back price", sans marge de bookmaker centralisee). Couverture par
  ligne : 92-100% (100% sur les six fichiers 2024/25, 92-95% sur les
  fichiers 2025/26 - degradation asymetrique deja observee pour d'autres
  bookmakers secondaires, ex. Pinnacle O/U). **SEUL INSTRUMENT LU ICI**
  (Phase G, hypothese exchange vs bookmaker).
- ``BFEAHH``/``BFEAHA`` (handicap asiatique, colonnes existantes,
  couverture identique a BFE 1X2/O-U) : **NON LU** - hors perimetre
  explicite de la Phase G (une seule variable nouvelle, jamais AH
  simultanement).
- ``BFCH/CD/CA``/``BFDCH/CD/CA`` (cloture Sportsbook) et
  ``BFECH/CD/CA``/``BFEC>2.5/C<2.5``/``BFECAHH/AHA`` (cloture Exchange) :
  **NON LUS** - aucune analyse retrospective (mouvement ouverture/
  cloture) n'est menee en Phase G, contrairement a E16.

Interpretation ("Betfair Sportsbook" vs "Betfair Exchange") deduite de
DEUX preuves structurelles independantes trouvees DANS les donnees
elles-memes (renommage inter-saison identique au precedent WH/LB deja
accepte ; signature d'overround radicalement differente entre les deux
instruments) - jamais une simple supposition sur le nom des colonnes.
Reste une HYPOTHESE DOCUMENTEE (meme discipline que la regle de
connaissance conservatrice, ADR 0006 section 4), pas un fait verifie
aupres de la source externe (aucune requete a football-data.co.uk
effectuee, aucune donnee supplementaire telechargee).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

SOURCE = "football_data"
BOOKMAKER = "B365"
MARKET = "1x2"
OVER_UNDER_25_MARKET = "over_under_2.5"
BOOKMAKERS_1X2 = ("B365", "BW", "PS", "WH", "LB")  # WH (2024/25) et LB (2025/26) mutuellement exclusifs

_ALLOWED_COLUMNS = (
    "Date",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "B365H",
    "B365D",
    "B365A",
    "BWH",
    "BWD",
    "BWA",
    "PSH",
    "PSD",
    "PSA",
    "B365>2.5",
    "B365<2.5",
    "P>2.5",
    "P<2.5",
    # Cotes de CLOTURE (E16) - reserve critique : jamais un feature de
    # decision a l'ouverture, voir docstring du module.
    "B365CH",
    "B365CD",
    "B365CA",
    "BWCH",
    "BWCD",
    "BWCA",
    "PSCH",
    "PSCD",
    "PSCA",
    "B365C>2.5",
    "B365C<2.5",
    "PC>2.5",
    "PC<2.5",
    # Statistiques de match (Phase F) - POST-kickoff, jamais un feature du
    # match qu'elles decrivent, voir la reserve de la docstring de module.
    "HST",
    "AST",
    # Betfair Exchange (Phase G) - PAS Betfair Sportsbook (BF/BFD, non lu,
    # voir docstring de module) ; ouverture uniquement, jamais AH ni
    # cloture.
    "BFEH",
    "BFED",
    "BFEA",
    "BFE>2.5",
    "BFE<2.5",
)

OVER_UNDER_25_BOOKMAKERS = ("B365", "P")  # P = Pinnacle (colonne distincte de PS, meme bookmaker - voir docstring)

# Colonnes lues SEULEMENT si presentes dans le fichier (E13/E16) - jamais
# une erreur si absentes du fichier entier, contrairement a _ALLOWED_COLUMNS.
_OPTIONAL_COLUMNS = (
    "WHH",
    "WHD",
    "WHA",
    "LBH",
    "LBD",
    "LBA",
    "WHCH",
    "WHCD",
    "WHCA",
    "LBCH",
    "LBCD",
    "LBCA",
)


@dataclass(frozen=True)
class FootballDataMatchRecord:
    league: str
    season: str
    source: str
    bookmaker: str
    market: str
    date_str: str
    time_str: str
    home_team_fd: str
    away_team_fd: str
    home_goals: int
    away_goals: int
    b365_home: float | None
    b365_draw: float | None
    b365_away: float | None
    b365_over_2_5: float | None = None
    b365_under_2_5: float | None = None
    p_over_2_5: float | None = None
    p_under_2_5: float | None = None
    # Tirs cadres (Phase F) - POST-kickoff, statistique de match, jamais une
    # cote. ``None`` uniquement pour compatibilite avec les constructions
    # directes anterieures a Phase F (ex : tests) qui ne les renseignent
    # pas - ``load_football_data_csv`` les remplit TOUJOURS (int, colonnes
    # _ALLOWED_COLUMNS, couverture 100% verifiee sur les six fichiers reels).
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None
    # Betfair EXCHANGE (Phase G) - PAS Betfair Sportsbook (BF/BFD, jamais
    # lu, voir docstring de module). Isole DELIBEREMENT de
    # `odds_1x2_by_bookmaker`/`over_under_2_5_by_bookmaker`/
    # `BOOKMAKERS_1X2` (methodes/tuple deja utilisees par E9/E13, gelees -
    # ne jamais alterer leur comportement en y ajoutant BFE) - accessible
    # uniquement via `bfe_odds_1x2()`/`bfe_over_under_2_5()`.
    bfe_home: float | None = None
    bfe_draw: float | None = None
    bfe_away: float | None = None
    bfe_over_2_5: float | None = None
    bfe_under_2_5: float | None = None
    bw_home: float | None = None
    bw_draw: float | None = None
    bw_away: float | None = None
    ps_home: float | None = None
    ps_draw: float | None = None
    ps_away: float | None = None
    wh_home: float | None = None
    wh_draw: float | None = None
    wh_away: float | None = None
    lb_home: float | None = None
    lb_draw: float | None = None
    lb_away: float | None = None
    # Cotes de CLOTURE (E16) - jamais un feature de decision a l'ouverture,
    # voir la reserve critique du docstring de module.
    b365_close_home: float | None = None
    b365_close_draw: float | None = None
    b365_close_away: float | None = None
    b365_close_over_2_5: float | None = None
    b365_close_under_2_5: float | None = None
    p_close_over_2_5: float | None = None
    p_close_under_2_5: float | None = None
    bw_close_home: float | None = None
    bw_close_draw: float | None = None
    bw_close_away: float | None = None
    ps_close_home: float | None = None
    ps_close_draw: float | None = None
    ps_close_away: float | None = None
    wh_close_home: float | None = None
    wh_close_draw: float | None = None
    wh_close_away: float | None = None
    lb_close_home: float | None = None
    lb_close_draw: float | None = None
    lb_close_away: float | None = None

    @property
    def has_complete_odds(self) -> bool:
        return self.b365_home is not None and self.b365_draw is not None and self.b365_away is not None

    @property
    def has_complete_over_under_2_5_odds(self) -> bool:
        return self.b365_over_2_5 is not None and self.b365_under_2_5 is not None

    @property
    def has_complete_p_over_under_2_5_odds(self) -> bool:
        return self.p_over_2_5 is not None and self.p_under_2_5 is not None

    def over_under_2_5_by_bookmaker(self) -> dict[str, dict[str, float]]:
        """{bookmaker: {"Over":.., "Under":..}} pour chaque bookmaker
        Over/Under 2.5 COMPLET sur ce match - un bookmaker absent ou
        partiel n'apparait simplement pas (jamais invente ni impute)."""
        out: dict[str, dict[str, float]] = {}
        if self.has_complete_over_under_2_5_odds:
            out["B365"] = {"Over": self.b365_over_2_5, "Under": self.b365_under_2_5}
        if self.has_complete_p_over_under_2_5_odds:
            out["P"] = {"Over": self.p_over_2_5, "Under": self.p_under_2_5}
        return out

    @property
    def has_complete_bw_odds(self) -> bool:
        return self.bw_home is not None and self.bw_draw is not None and self.bw_away is not None

    @property
    def has_complete_ps_odds(self) -> bool:
        return self.ps_home is not None and self.ps_draw is not None and self.ps_away is not None

    @property
    def has_complete_wh_odds(self) -> bool:
        return self.wh_home is not None and self.wh_draw is not None and self.wh_away is not None

    @property
    def has_complete_lb_odds(self) -> bool:
        return self.lb_home is not None and self.lb_draw is not None and self.lb_away is not None

    def odds_1x2_by_bookmaker(self) -> dict[str, dict[str, float]]:
        """{bookmaker: {"H":.., "D":.., "A":..}} pour chaque bookmaker
        1X2 COMPLET sur ce match - un bookmaker absent ou partiel sur ce
        match n'apparait simplement pas (jamais invente ni impute). WH et
        LB ne sont jamais simultanement presents (mutuellement exclusifs
        par saison, voir docstring du module)."""
        out: dict[str, dict[str, float]] = {}
        if self.has_complete_odds:
            out["B365"] = {"H": self.b365_home, "D": self.b365_draw, "A": self.b365_away}
        if self.has_complete_bw_odds:
            out["BW"] = {"H": self.bw_home, "D": self.bw_draw, "A": self.bw_away}
        if self.has_complete_ps_odds:
            out["PS"] = {"H": self.ps_home, "D": self.ps_draw, "A": self.ps_away}
        if self.has_complete_wh_odds:
            out["WH"] = {"H": self.wh_home, "D": self.wh_draw, "A": self.wh_away}
        if self.has_complete_lb_odds:
            out["LB"] = {"H": self.lb_home, "D": self.lb_draw, "A": self.lb_away}
        return out

    # ----------------------------------------------------------------
    # Betfair EXCHANGE (Phase G) - DELIBEREMENT ISOLE de
    # `odds_1x2_by_bookmaker`/`over_under_2_5_by_bookmaker`/
    # `BOOKMAKERS_1X2` (deja utilises par E9/E13, geles - toute
    # modification de leur comportement romprait leur reproductibilite
    # si ces scripts etaient re-executes). Accessible uniquement via ces
    # deux methodes dediees.
    # ----------------------------------------------------------------

    @property
    def has_complete_bfe_odds(self) -> bool:
        return self.bfe_home is not None and self.bfe_draw is not None and self.bfe_away is not None

    @property
    def has_complete_bfe_over_under_2_5_odds(self) -> bool:
        return self.bfe_over_2_5 is not None and self.bfe_under_2_5 is not None

    def bfe_odds_1x2(self) -> dict[str, float] | None:
        """{"H":.., "D":.., "A":..} si Betfair Exchange 1X2 est COMPLET
        sur ce match, sinon ``None`` (jamais invente ni impute - BFE est
        absent sur ~5-8% des matchs 2025/26, voir docstring de module)."""
        return (
            {"H": self.bfe_home, "D": self.bfe_draw, "A": self.bfe_away}
            if self.has_complete_bfe_odds
            else None
        )

    def bfe_over_under_2_5(self) -> dict[str, float] | None:
        """{"Over":.., "Under":..} si Betfair Exchange Over/Under 2.5 est
        COMPLET sur ce match, sinon ``None``."""
        return (
            {"Over": self.bfe_over_2_5, "Under": self.bfe_under_2_5}
            if self.has_complete_bfe_over_under_2_5_odds
            else None
        )

    # ----------------------------------------------------------------
    # Cotes de CLOTURE (E16) - RETROSPECTIF UNIQUEMENT. Jamais utilisees
    # comme feature d'une decision a l'ouverture (voir reserve critique
    # du docstring de module) - servent uniquement a etudier le
    # mouvement de marche ouverture -> cloture, apres coup.
    # ----------------------------------------------------------------

    @property
    def has_complete_close_odds(self) -> bool:
        return self.b365_close_home is not None and self.b365_close_draw is not None and self.b365_close_away is not None

    @property
    def has_complete_close_over_under_2_5_odds(self) -> bool:
        return self.b365_close_over_2_5 is not None and self.b365_close_under_2_5 is not None

    @property
    def has_complete_p_close_over_under_2_5_odds(self) -> bool:
        return self.p_close_over_2_5 is not None and self.p_close_under_2_5 is not None

    @property
    def has_complete_bw_close_odds(self) -> bool:
        return self.bw_close_home is not None and self.bw_close_draw is not None and self.bw_close_away is not None

    @property
    def has_complete_ps_close_odds(self) -> bool:
        return self.ps_close_home is not None and self.ps_close_draw is not None and self.ps_close_away is not None

    @property
    def has_complete_wh_close_odds(self) -> bool:
        return self.wh_close_home is not None and self.wh_close_draw is not None and self.wh_close_away is not None

    @property
    def has_complete_lb_close_odds(self) -> bool:
        return self.lb_close_home is not None and self.lb_close_draw is not None and self.lb_close_away is not None

    def closing_odds_1x2_by_bookmaker(self) -> dict[str, dict[str, float]]:
        """Miroir EXACT de ``odds_1x2_by_bookmaker`` pour les cotes de
        CLOTURE - meme convention (bookmaker absent/partiel simplement
        absent, jamais invente). RETROSPECTIF UNIQUEMENT."""
        out: dict[str, dict[str, float]] = {}
        if self.has_complete_close_odds:
            out["B365"] = {"H": self.b365_close_home, "D": self.b365_close_draw, "A": self.b365_close_away}
        if self.has_complete_bw_close_odds:
            out["BW"] = {"H": self.bw_close_home, "D": self.bw_close_draw, "A": self.bw_close_away}
        if self.has_complete_ps_close_odds:
            out["PS"] = {"H": self.ps_close_home, "D": self.ps_close_draw, "A": self.ps_close_away}
        if self.has_complete_wh_close_odds:
            out["WH"] = {"H": self.wh_close_home, "D": self.wh_close_draw, "A": self.wh_close_away}
        if self.has_complete_lb_close_odds:
            out["LB"] = {"H": self.lb_close_home, "D": self.lb_close_draw, "A": self.lb_close_away}
        return out

    def closing_over_under_2_5_by_bookmaker(self) -> dict[str, dict[str, float]]:
        """Miroir EXACT de ``over_under_2_5_by_bookmaker`` pour les cotes
        de CLOTURE (B365 et P uniquement - aucune colonne de cloture O/U
        n'existe pour BW/WH/LB dans les fichiers sources). RETROSPECTIF
        UNIQUEMENT."""
        out: dict[str, dict[str, float]] = {}
        if self.has_complete_close_over_under_2_5_odds:
            out["B365"] = {"Over": self.b365_close_over_2_5, "Under": self.b365_close_under_2_5}
        if self.has_complete_p_close_over_under_2_5_odds:
            out["P"] = {"Over": self.p_close_over_2_5, "Under": self.p_close_under_2_5}
        return out


def _parse_optional_float(raw: str) -> float | None:
    """Parse une cote decimale, ou ``None`` si la cellule est vide OU si
    la valeur brute n'est pas une cote decimale valide (``<= 1.0``,
    impossible pour une vraie cote - meme definition que
    ``market_engine.overround.validate_odds``). CONSTAT EMPIRIQUE (E13,
    inspection directe) : un match (Paris SG-Le Havre, F1 2024/25,
    19/04/2025) porte litteralement ``"0"`` dans ``P>2.5``/``P<2.5``
    (et leurs equivalents de cloture) - le sentinelle Football-Data pour
    "cote non collectee" sur CE bookmaker precis, distinct d'une cellule
    vide mais avec la meme signification. Traite comme absent, jamais
    comme une cote reelle de 0.0."""
    if raw is None or raw.strip() == "":
        return None
    value = float(raw)
    return value if value > 1.0 else None


def load_football_data_csv(path: Path, league: str, season: str) -> list[FootballDataMatchRecord]:
    """Lit un fichier Football-Data brut et ne retient QUE les colonnes de
    ``_ALLOWED_COLUMNS`` (toujours requises - echec explicite si absentes)
    et de ``_OPTIONAL_COLUMNS`` (lues seulement si presentes DANS CE
    FICHIER - jamais une erreur si absentes, jamais une valeur inventee
    pour une colonne manquante)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [c for c in _ALLOWED_COLUMNS if c not in fieldnames]
        if missing:
            raise ValueError(f"{path}: colonnes attendues absentes du fichier : {missing}.")
        present_optional = {c for c in _OPTIONAL_COLUMNS if c in fieldnames}

        def _optional(row: dict, column: str) -> float | None:
            return _parse_optional_float(row[column]) if column in present_optional else None

        records: list[FootballDataMatchRecord] = []
        for row in reader:
            records.append(
                FootballDataMatchRecord(
                    league=league,
                    season=season,
                    source=SOURCE,
                    bookmaker=BOOKMAKER,
                    market=MARKET,
                    date_str=row["Date"],
                    time_str=row["Time"],
                    home_team_fd=row["HomeTeam"],
                    away_team_fd=row["AwayTeam"],
                    home_goals=int(row["FTHG"]),
                    away_goals=int(row["FTAG"]),
                    b365_home=_parse_optional_float(row["B365H"]),
                    b365_draw=_parse_optional_float(row["B365D"]),
                    b365_away=_parse_optional_float(row["B365A"]),
                    b365_over_2_5=_parse_optional_float(row["B365>2.5"]),
                    b365_under_2_5=_parse_optional_float(row["B365<2.5"]),
                    p_over_2_5=_parse_optional_float(row["P>2.5"]),
                    p_under_2_5=_parse_optional_float(row["P<2.5"]),
                    home_shots_on_target=int(row["HST"]),
                    away_shots_on_target=int(row["AST"]),
                    bfe_home=_parse_optional_float(row["BFEH"]),
                    bfe_draw=_parse_optional_float(row["BFED"]),
                    bfe_away=_parse_optional_float(row["BFEA"]),
                    bfe_over_2_5=_parse_optional_float(row["BFE>2.5"]),
                    bfe_under_2_5=_parse_optional_float(row["BFE<2.5"]),
                    bw_home=_parse_optional_float(row["BWH"]),
                    bw_draw=_parse_optional_float(row["BWD"]),
                    bw_away=_parse_optional_float(row["BWA"]),
                    ps_home=_parse_optional_float(row["PSH"]),
                    ps_draw=_parse_optional_float(row["PSD"]),
                    ps_away=_parse_optional_float(row["PSA"]),
                    wh_home=_optional(row, "WHH"),
                    wh_draw=_optional(row, "WHD"),
                    wh_away=_optional(row, "WHA"),
                    lb_home=_optional(row, "LBH"),
                    lb_draw=_optional(row, "LBD"),
                    lb_away=_optional(row, "LBA"),
                    b365_close_home=_parse_optional_float(row["B365CH"]),
                    b365_close_draw=_parse_optional_float(row["B365CD"]),
                    b365_close_away=_parse_optional_float(row["B365CA"]),
                    b365_close_over_2_5=_parse_optional_float(row["B365C>2.5"]),
                    b365_close_under_2_5=_parse_optional_float(row["B365C<2.5"]),
                    p_close_over_2_5=_parse_optional_float(row["PC>2.5"]),
                    p_close_under_2_5=_parse_optional_float(row["PC<2.5"]),
                    bw_close_home=_parse_optional_float(row["BWCH"]),
                    bw_close_draw=_parse_optional_float(row["BWCD"]),
                    bw_close_away=_parse_optional_float(row["BWCA"]),
                    ps_close_home=_parse_optional_float(row["PSCH"]),
                    ps_close_draw=_parse_optional_float(row["PSCD"]),
                    ps_close_away=_parse_optional_float(row["PSCA"]),
                    wh_close_home=_optional(row, "WHCH"),
                    wh_close_draw=_optional(row, "WHCD"),
                    wh_close_away=_optional(row, "WHCA"),
                    lb_close_home=_optional(row, "LBCH"),
                    lb_close_draw=_optional(row, "LBCD"),
                    lb_close_away=_optional(row, "LBCA"),
                )
            )
    return records
