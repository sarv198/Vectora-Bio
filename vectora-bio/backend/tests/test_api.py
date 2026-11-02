import pytest
from fastapi.testclient import TestClient

from app.data.profile_store import get_profile_store
from app.db.session import get_session_factory
from app.services.evaluation_service import run_moa_benchmark
from tests import synthetic

ANALYSIS_REQUESTS = [
    ("/api/similarity/compounds", {"compound_id": "CMPD_A1"}),
    ("/api/targets/prioritize", {"compound_id": "CMPD_A1"}),
    ("/api/moa/infer", {"compound_id": "CMPD_A1"}),
    ("/api/rescue/search", {"perturbation_id": "GUIDE_G3"}),
]


# --- No data imported -------------------------------------------------------------


def test_health_without_data(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["database"]["compound_count"] == 0
    assert [d["available"] for d in body["datasets"]] == [False, False, False]


@pytest.mark.parametrize("path", ["/api/compounds", "/api/compounds/CMPD_A1", "/api/genes", "/api/genes/1001"])
def test_metadata_endpoints_report_data_not_loaded(client, path):
    response = client.get(path)
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "data_not_loaded"
    assert body["details"]["missing_datasets"]
    assert "import" in body["details"]["hint"]


@pytest.mark.parametrize(("path", "payload"), ANALYSIS_REQUESTS)
def test_analysis_endpoints_report_data_not_loaded(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 503
    assert response.json()["error"] == "data_not_loaded"
    assert response.json()["details"]["missing_datasets"] == ["compound_profiles"]


def test_evaluation_without_results(client):
    body = client.get("/api/evaluation").json()
    assert body["results"] == []
    assert "No evaluation results" in body["message"]


def test_request_validation(client):
    assert client.post("/api/similarity/compounds", json={"compound_id": ""}).status_code == 422
    assert client.post("/api/rescue/search", json={}).status_code == 422


def test_cors_and_openapi(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    paths = client.get("/openapi.json").json()["paths"]
    for path in ["/api/health", "/api/compounds/{compound_id}", "/api/genes/{gene_id}", "/api/evaluation"]:
        assert path in paths
    for path, _ in ANALYSIS_REQUESTS:
        assert path in paths


def test_database_unavailable(monkeypatch, settings):
    from tests.conftest import _clear_caches

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@127.0.0.1:1/none")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_S", "1")
    _clear_caches()
    from app.main import create_app

    with TestClient(create_app()) as client:
        health = client.get("/api/health").json()
        assert health["status"] == "degraded"
        assert health["database"]["status"] == "unavailable"
        response = client.get("/api/compounds")
        assert response.status_code == 503
        assert response.json()["error"] == "database_unavailable"


# --- Synthetic data imported ------------------------------------------------------


def test_health_with_data(client, loaded_data):
    body = client.get("/api/health").json()
    assert body["database"]["compound_count"] == 7
    assert body["database"]["genetic_perturbation_count"] == 4
    assert all(d["available"] for d in body["datasets"])
    assert body["datasets"][0]["n_features"] == synthetic.N_FEATURES


def test_compound_endpoints(client, loaded_data):
    page = client.get("/api/compounds", params={"search": "cmpd_a", "limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get("/api/compounds", params={"moa": "class_y"}).json()["total"] == 2
    assert client.get("/api/compounds", params={"search": "nothing"}).json()["total"] == 0

    detail = client.get("/api/compounds/CMPD_A1").json()
    assert detail["known_target"] == "GENE1"
    assert detail["contexts"][0]["replicate_count"] == 3
    missing = client.get("/api/compounds/NOPE")
    assert missing.status_code == 404 and missing.json()["error"] == "not_found"


def test_gene_endpoints(client, loaded_data):
    assert client.get("/api/genes", params={"perturbation_type": "crispr"}).json()["total"] == 3
    by_id = client.get("/api/genes/1001").json()
    by_symbol = client.get("/api/genes/gene1").json()
    assert by_id == by_symbol
    assert len(by_id["perturbations"]) == 2
    assert client.get("/api/genes/9999").status_code == 404


def test_similarity(client, loaded_data):
    response = client.post("/api/similarity/compounds", json={"compound_id": "CMPD_A1", "top_k": 3})
    assert response.status_code == 200, response.json()
    body = response.json()
    assert {p["candidate_id"] for p in body["predictions"][:2]} == {"CMPD_A2", "CMPD_A3"}
    assert [p["rank"] for p in body["predictions"]] == [1, 2, 3]
    assert body["summary"] == {"n_candidates": 6, "n_features": 12, "cell_line": "CELL_A", "timepoint": 48.0}
    evidence_types = {e["evidence_type"] for e in body["predictions"][0]["supporting_evidence"]}
    assert evidence_types == {"phenotypic_similarity", "annotation"}
    assert body["run_id"] is not None


def test_similarity_errors(client, loaded_data):
    assert client.post("/api/similarity/compounds", json={"compound_id": "NOPE"}).status_code == 404
    response = client.post("/api/similarity/compounds", json={"compound_id": "CMPD_A1", "cell_line": "OTHER"})
    assert response.status_code == 400
    assert response.json()["details"]["available_contexts"][0]["cell_line"] == "CELL_A"
    response = client.post("/api/similarity/compounds", json={"compound_id": "CMPD_A1", "top_k": 100000})
    assert response.status_code == 400


def test_target_prioritization(client, loaded_data):
    body = client.post("/api/targets/prioritize", json={"compound_id": "CMPD_A1"}).json()
    top = body["predictions"][0]
    assert top["candidate_id"] == "GENE1"
    evidence = top["supporting_evidence"]
    assert {e["source_id"] for e in evidence if e["evidence_type"] == "genetic_perturbation_match"} == {
        "GUIDE_G1_1",
        "GUIDE_G1_2",
    }
    assert any(e["evidence_type"] == "annotation" for e in evidence)

    # CMPD_B1 anti-correlates with the ORF_G2 profile: surfaced with |cosine|, last when signed.
    absolute = client.post("/api/targets/prioritize", json={"compound_id": "CMPD_B1"}).json()
    assert absolute["predictions"][0]["candidate_id"] == "GENE2"
    signed = client.post(
        "/api/targets/prioritize", json={"compound_id": "CMPD_B1", "use_absolute_similarity": False}
    ).json()
    assert signed["predictions"][-1]["candidate_id"] == "GENE2"
    crispr_only = client.post(
        "/api/targets/prioritize", json={"compound_id": "CMPD_B1", "perturbation_types": ["crispr"]}
    ).json()
    assert "GENE2" not in {p["candidate_id"] for p in crispr_only["predictions"]}


def test_moa_inference(client, loaded_data):
    body = client.post("/api/moa/infer", json={"compound_id": "CMPD_A1", "n_neighbors": 3}).json()
    assert body["predictions"][0]["candidate_id"] == "class_x"
    assert body["predictions"][0]["score"] == pytest.approx(1.0)
    assert "own annotation was not used" in body["message"]
    sources = {e["source_id"] for e in body["predictions"][0]["supporting_evidence"]}
    assert "CMPD_A1" not in sources


def test_rescue_search(client, loaded_data):
    body = client.post("/api/rescue/search", json={"perturbation_id": "GUIDE_G3"}).json()
    assert body["predictions"][0]["candidate_id"] == "CMPD_C"
    assert body["predictions"][0]["score"] > 0.9
    assert body["query_id"] == "GUIDE_G3"

    no_controls = client.post(
        "/api/rescue/search", json={"perturbation_id": "GUIDE_G3", "subtract_matched_controls": False}
    ).json()
    assert no_controls["predictions"][0]["candidate_id"] == "CMPD_C"

    signature = {feature: 0.0 for feature in synthetic.FEATURES}
    signature["feat_002"] = 1.0
    custom = client.post("/api/rescue/search", json={"signature": signature}).json()
    assert custom["query_id"] == "custom_signature"
    assert custom["predictions"][0]["candidate_id"] == "CMPD_C"

    response = client.post("/api/rescue/search", json={"signature": {"feat_000": 1.0}})
    assert response.status_code == 409 and response.json()["error"] == "feature_mismatch"
    zero = client.post("/api/rescue/search", json={"signature": {f: 0.0 for f in synthetic.FEATURES}})
    assert zero.status_code == 400
    assert client.post("/api/rescue/search", json={"perturbation_id": "NOPE"}).status_code == 404


def test_evaluation_results_after_benchmark(client, loaded_data):
    with get_session_factory()() as db:
        results = run_moa_benchmark(get_profile_store(), db, cell_line=None, timepoint=None, n_neighbors=3, k=2)
    names = {r.metric_name for r in results}
    assert {"moa_top1_accuracy", "mean_precision_at_2", "mean_recall_at_2", "mean_ndcg_at_2"} <= names
    body = client.get("/api/evaluation").json()
    assert len(body["results"]) == len(results)
    assert body["message"] is None
    assert body["results"][0]["parameters"]["n_neighbors"] == 3
