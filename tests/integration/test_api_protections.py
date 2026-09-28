"""Garde-fous obligatoires (Phase UI-2-B) pour ``sys_foot_quant.api`` -
verifie le COMPORTEMENT et la STRUCTURE effective de l'application (routes
enregistrees, schema OpenAPI reel), jamais seulement des noms de
fonctions. Aucun de ces tests n'appelle le moteur ni ne modifie de fichier
canonique."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sys_foot_quant.api import app as app_module
from sys_foot_quant.api import routes_matches, routes_prediction, routes_shadow
from sys_foot_quant.api.app import DEFAULT_HOST, app

client = TestClient(app)

_API_DIR = Path(app_module.__file__).resolve().parent
_API_MODULE_FILES = [p for p in _API_DIR.glob("*.py") if p.name != "__init__.py"]

# ``run_prediction``/``predict_match`` sont retires de cette liste : leur
# usage est desormais explicitement autorise, mais UNIQUEMENT encapsule
# derriere ``prediction_adapter.py`` (voir les 2 tests dedies plus bas, qui
# verifient precisement cette encapsulation plutot que d'interdire le token
# partout).
_FORBIDDEN_TRAINING_TOKENS = (
    "build_match_train_dataframes",
    "build_prediction_inputs",
    "build_real_match_records",
    "build_real_match_records_multi_season",
    "run_match_decision",
)
_FORBIDDEN_WRITE_TOKENS = ("record_prediction", "settle_prediction")


# --- routes reellement enregistrees (introspection du schema OpenAPI reel) --


def test_only_the_six_authorized_get_routes_are_exposed() -> None:
    """Introspecte le schema OpenAPI REEL genere par l'application
    (comportement effectif, pas une simple lecture du code source) -
    aucune route en dehors des 6 autorisees (les 5 routes UI-2-B plus la
    route de prediction explicitement autorisee), aucune methode
    d'ecriture."""
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    business_paths = {p: methods for p, methods in paths.items() if p not in ("/openapi.json",)}
    assert set(business_paths.keys()) == {
        "/matches",
        "/matches/{match_id}",
        "/matches/{match_id}/prediction",
        "/shadow",
        "/shadow/{prediction_id}",
        "/performance",
    }
    for path, methods in business_paths.items():
        assert set(methods.keys()) == {"get"}, f"Methode non-GET exposee sur {path} : {set(methods.keys())}"


def test_no_data_quality_route_exists() -> None:
    schema = client.get("/openapi.json").json()
    assert "/data-quality" not in schema["paths"]


def test_only_the_authorized_prediction_route_has_a_prediction_segment() -> None:
    """Le seul segment de route evoquant une prediction doit etre la route
    explicitement autorisee ``/matches/{match_id}/prediction``, en GET
    uniquement - aucune autre route (existante ou ajoutee ulterieurement)
    ne doit exposer un segment ``predict``/``decision`` evoquant le
    lancement d'une prediction."""
    schema = client.get("/openapi.json").json()
    authorized_path = "/matches/{match_id}/prediction"

    assert authorized_path in schema["paths"], "La route de prediction autorisee est absente du schema OpenAPI."
    assert set(schema["paths"][authorized_path].keys()) == {"get"}, (
        f"La route de prediction autorisee expose une methode non-GET : {set(schema['paths'][authorized_path].keys())}"
    )

    forbidden_segments = ("predict", "decision")
    for path in schema["paths"]:
        if path == authorized_path:
            continue
        segments = [s for s in path.lower().split("/") if s and not (s.startswith("{") and s.endswith("}"))]
        for segment in segments:
            for fragment in forbidden_segments:
                assert fragment not in segment, f"Route suspecte de lancer une prediction : {path} (segment {segment!r})"


def test_no_shadow_write_route_exists() -> None:
    """Verifie via le schema OpenAPI REEL (genere dynamiquement par
    l'application a partir des routes effectivement enregistrees) qu'
    aucune methode d'ecriture n'est enregistree sur /shadow* - et confirme
    directement, en envoyant de veritables requetes, que ces methodes sont
    refusees si elles etaient tentees."""
    schema = client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if path.startswith("/shadow"):
            assert set(methods.keys()) == {"get"}, f"Methode d'ecriture exposee sur {path} : {set(methods.keys())}"

    concrete_shadow_path = "/shadow/some-id"
    for method, client_call in (
        ("POST", client.post),
        ("PUT", client.put),
        ("PATCH", client.patch),
        ("DELETE", client.delete),
    ):
        response = client_call(concrete_shadow_path)
        assert response.status_code == 405, f"{method} {concrete_shadow_path} aurait du etre refuse (405)."


def test_no_min_edge_threshold_or_scientific_threshold_parameter_in_openapi_schema() -> None:
    """Introspecte les PARAMETRES REELS de chaque route via le schema
    OpenAPI genere - jamais une simple recherche textuelle sur le code
    source, qui pourrait manquer un parametre genere dynamiquement."""
    schema = client.get("/openapi.json").json()
    forbidden = ("min_edge_threshold", "operational_thresholds", "edge_threshold")
    for path, methods in schema["paths"].items():
        for method_schema in methods.values():
            for param in method_schema.get("parameters", []):
                name = param.get("name", "").lower()
                for token in forbidden:
                    assert token not in name, f"Parametre scientifique expose : {path} -> {param.get('name')}"


# --- absence d'import des fonctions d'entrainement/prediction/ecriture -----


def test_api_modules_never_import_training_dataframe_construction_functions() -> None:
    for path in _API_MODULE_FILES:
        source = path.read_text()
        import_lines = [
            line for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            for token in _FORBIDDEN_TRAINING_TOKENS:
                assert token not in line, f"{path.name} importe {token!r} (ligne : {line!r})."


def test_predict_match_script_is_only_referenced_inside_the_prediction_adapter() -> None:
    """``scripts/predict_match.py`` (le script moteur, INCHANGE) ne doit
    jamais etre importe/charge directement en dehors de
    ``prediction_adapter.py`` - seul module explicitement autorise a le
    charger (mecanisme ``importlib`` deja utilise par les tests existants).
    Tout autre module de l'API qui a besoin de ``run_prediction`` doit
    l'importer DEPUIS ``prediction_adapter`` (indirection sanctionnee),
    jamais en re-chargeant le script lui-meme."""
    adapter_path = _API_DIR / "prediction_adapter.py"
    for path in _API_MODULE_FILES:
        if path == adapter_path:
            continue
        source = path.read_text()
        import_lines = [
            line for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            assert "predict_match" not in line, (
                f"{path.name} reference directement 'predict_match' (ligne : {line!r}) - "
                "seul prediction_adapter.py a le droit de charger scripts/predict_match.py."
            )


def test_routes_prediction_imports_run_prediction_from_the_adapter_only() -> None:
    """Verifie que ``routes_prediction.py`` obtient ``run_prediction``
    EXCLUSIVEMENT en l'important depuis ``prediction_adapter`` (indirection
    sanctionnee) - jamais via une autre source (import direct du script,
    reimplementation locale, etc.)."""
    source = Path(routes_prediction.__file__).read_text()
    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    matching_lines = [line for line in import_lines if "run_prediction" in line]
    assert matching_lines, "routes_prediction.py n'importe pas 'run_prediction'."
    for line in matching_lines:
        assert "prediction_adapter" in line, (
            f"routes_prediction.py importe 'run_prediction' hors de prediction_adapter.py (ligne : {line!r})."
        )


def test_api_modules_never_import_shadow_write_functions() -> None:
    for path in _API_MODULE_FILES:
        source = path.read_text()
        import_lines = [
            line for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            for token in _FORBIDDEN_WRITE_TOKENS:
                assert token not in line, f"{path.name} importe {token!r} (ligne : {line!r})."


def test_route_modules_do_not_call_the_engine_directly() -> None:
    """Garde-fou comportemental : les modules de routes n'importent que
    ``match_catalog``/``shadow_mode.journal`` - jamais
    ``final_engine``."""
    for path in (Path(routes_matches.__file__), Path(routes_shadow.__file__)):
        source = path.read_text()
        assert "final_engine" not in source


# --- configuration reseau ----------------------------------------------------


def test_default_host_is_localhost_never_all_interfaces() -> None:
    assert DEFAULT_HOST == "127.0.0.1"
    assert DEFAULT_HOST != "0.0.0.0"


# --- absence d'effet de bord sur les fichiers canoniques --------------------


def test_reading_any_route_never_modifies_canonical_data_files() -> None:
    canonical_files = list(Path("research/xg_feasibility/runs").glob("*.json"))
    contents_before = {p: p.read_bytes() for p in canonical_files}

    client.get("/matches", params={"competition": "ligue1", "season": "2026_27"})
    client.get("/matches/31975", params={"competition": "ligue1", "season": "2026_27"})
    client.get("/shadow")
    client.get("/performance")

    for p in canonical_files:
        assert p.read_bytes() == contents_before[p]
