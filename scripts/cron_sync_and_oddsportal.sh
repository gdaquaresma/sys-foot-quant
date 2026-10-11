#!/bin/bash
# Script d'orchestration pour la tache planifiee locale (launchd) -
# Etape 1 : resync Understat (fiable) pour ligue1/liga/premier_league.
# Etape 2 : fetch OddsPortal best-effort (fiabilite non garantie, voir
# docs/oddsportal_integration_note.md) pour les 3 memes competitions.
#
# Discipline fail-tolerant explicite : chaque competition, a chaque etape,
# est executee INDEPENDAMMENT des autres (jamais de "set -e" global) - un
# echec reseau/parsing sur une competition ne doit JAMAIS empecher les
# autres competitions ni l'autre etape de s'executer. Rien n'est jamais
# fabrique en cas d'echec (voir fail-closed de cli_sync_current_season.py/
# cli_fetch_oddsportal_results.py eux-memes) - ce script ne fait
# qu'orchestrer des appels independants et journaliser leur issue.
#
# IMPORTANT (--league-id) : "Ligue 1" est CONFIRME par capture navigateur
# reelle (voir research/xg_feasibility/current_season_updater.py). "EPL"
# et "La Liga" sont des VALEURS NON CONFIRMEES par capture reseau reelle
# pour l'endpoint getLeagueData (seule Ligue 1 a ete verifiee a ce jour) -
# si la synchronisation liga/premier_league echoue systematiquement dans
# le log, verifier/ajuster ces deux valeurs en priorite (cf. le
# raisonnement documente dans current_season_updater.py : la convention
# ancienne page HTML "La_liga"/"EPL" (underscore) peut differer de celle
# attendue par ce nouvel endpoint JSON, par analogie avec "Ligue_1" ->
# "Ligue 1").

set -u  # variable non definie = erreur immediate (mais pas "set -e" :
        # chaque commande ci-dessous gere son propre code de retour).

REPO_DIR="/Users/gda/sys-foot-quant"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/cron_sync_and_oddsportal.log"
mkdir -p "$LOG_DIR"

cd "$REPO_DIR" || { echo "$(date -u +%FT%TZ) ERREUR : impossible de cd vers $REPO_DIR" >> "$LOG_FILE"; exit 1; }

UV_BIN="/Users/gda/.local/bin/uv"

log() {
    echo "$(date -u +%FT%TZ) $1" >> "$LOG_FILE"
}

log "=== Debut du passage cron (resync Understat + fetch OddsPortal) ==="

# --- Etape 1 : resync Understat (fiable) ------------------------------------

sync_one() {
    local competition="$1"
    local league_id="$2"
    local canonical_path="$3"
    log "[Understat] $competition : debut (league-id=$league_id)"
    if "$UV_BIN" run python -m research.xg_feasibility.cli_sync_current_season \
        --competition "$competition" --league-id "$league_id" --season 2026 \
        --canonical-path "$canonical_path" >> "$LOG_FILE" 2>&1; then
        log "[Understat] $competition : OK"
    else
        log "[Understat] $competition : ECHEC (code $?) - fichier canonique non modifie (fail-closed), ignore, passage au suivant"
    fi
}

sync_one "ligue1" "Ligue 1" "research/xg_feasibility/runs/ligue1_2026_datesData.json"
sync_one "liga" "La Liga" "research/xg_feasibility/runs/liga_2026_datesData.json"
sync_one "premier_league" "EPL" "research/xg_feasibility/runs/epl_2026_datesData.json"

# --- Etape 2 : fetch OddsPortal (best-effort, echecs tolerees) --------------

fetch_oddsportal_one() {
    local competition="$1"
    log "[OddsPortal] $competition : debut"
    if "$UV_BIN" run python -m research.oddsportal_integration.cli_fetch_oddsportal_results \
        --competition "$competition" >> "$LOG_FILE" 2>&1; then
        log "[OddsPortal] $competition : OK"
    else
        log "[OddsPortal] $competition : ECHEC (fiabilite non garantie, voir docs/oddsportal_integration_note.md) - ignore, passage au suivant"
    fi
}

fetch_oddsportal_one "ligue1"
fetch_oddsportal_one "liga"
fetch_oddsportal_one "premier_league"

log "=== Fin du passage cron ==="
