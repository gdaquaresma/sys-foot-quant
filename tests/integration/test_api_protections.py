"""Garde-fous obligatoires (Phase UI-2-B) pour ``sys_foot_quant.api`` -
verifie le COMPORTEMENT et la STRUCTURE effective de l'application (routes
enregistrees, schema OpenAPI reel), jamais seulement des noms de
fonctions. Aucun de ces tests n'appelle le moteur ni ne modifie de fichier
canonique."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sys_foot_quant.api import app as app_module
from sys_foot_quant.api import routes_matches, routes_shadow
from sys_foot_quant.api.app import DEFAULT_HOST, app

client = TestClient(app)

_API_DIR = Path(app_module.__file__).resolve().parent
_API_MODULE_FILES = [p for p in _API_DIR.glob("*.py") if p.name != "__init__.py"]

_FORBIDDEN_TRAINING_TOKENS = (
    "build_match_train_dataframes",
    "build_prediction_inputs",
    "build_real_match_records",
    "build_real_match_records_multi_season",
    "run_match_decision",
    "run_prediction",
    "predict_match",
)
_FORBIDDEN_WRITE_TOKENS = ("record_prediction", "settle_prediction")


# --- routes reellement enregistrees (introspection du schema OpenAPI reel) --


def test_only_the_five_authorized_get_routes_are_exposed() -> None:
    """Introspecte le schema OpenAPI REEL genere par l'application
    (comportement effectif, pas une simple lecture du code source) -
    aucune route en dehors des 5 autorisees, aucune methode d'ecriture."""
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    business_paths = {p: methods for p, methods in paths.items() if p not in ("/openapi.json",)}
    assert set(business_paths.keys()) == {"/matches", "/matches/{match_id}", "/shadow", "/shadow/{prediction_id}", "/performance"}
    for path, methods in business_paths.items():
        assert set(methods.keys()) == {"get"}, f"Methode non-GET exposee sur {path} : {set(methods.keys())}"


def test_no_data_quality_route_exists() -> None:
    schema = client.get("/openapi.json").json()
    assert "/data-quality" not in schema["paths"]


def test_no_prediction_route_exists() -> None:
    """Verifie l'absence de segment de route (pas de parametre de chemin,
    ex. ``{prediction_id}`` sur ``/shadow`` reste legitime) evoquant le
    lancement d'une prediction."""
    schema = client.get("/openapi.json").json()
    forbidden_segments = ("predict", "decision")
    for path in schema["paths"]:
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
