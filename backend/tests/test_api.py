import pytest
from conftest import FakeProvider
from fastapi.testclient import TestClient

from triage import api
from triage.classifier import TriageClassifier
from triage.config import get_settings


@pytest.fixture
def client(sample_output_json):
    def _fake_classifier():
        return TriageClassifier(get_settings(), provider=FakeProvider([sample_output_json] * 20))

    api.app.dependency_overrides[api.get_classifier] = _fake_classifier
    with TestClient(api.app) as c:
        yield c
    api.app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_triage_success(client):
    resp = client.post("/triage", json={"id": 1, "mensagem": "Temos interesse em crédito PJ."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo_solicitacao"] == "interesse_em_credito_pj"
    assert "X-Trace-Id" in resp.headers


def test_triage_validation_error(client):
    resp = client.post("/triage", json={"id": 1, "mensagem": ""})
    assert resp.status_code == 422


def test_triage_batch(client):
    resp = client.post(
        "/triage/batch",
        json=[{"id": 1, "mensagem": "crédito"}, {"id": 2, "mensagem": "outra mensagem"}],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_dashboard_endpoints_after_run(client):
    client.post("/triage", json={"id": 1, "mensagem": "Temos interesse em crédito PJ."})
    runs = client.get("/runs")
    assert runs.status_code == 200
    assert runs.json()["total"] >= 1

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["total_runs"] >= 1

    timeline = client.get("/metrics/timeline")
    assert timeline.status_code == 200
    assert isinstance(timeline.json(), list)


def test_pending_reports_counts_unevaluated_runs(client):
    # A fresh run has no evaluation yet, so it shows up as pending.
    client.post("/triage", json={"id": 1, "mensagem": "Temos interesse em crédito PJ."})
    resp = client.get("/reports/pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending"] >= 1
    assert len(body["run_ids"]) == body["pending"]


def test_run_reports_with_no_pending_returns_zero(client):
    # No runs at all -> nothing to judge (no real LLM call), aggregate still refreshes.
    resp = client.post("/reports/run", json={"limit": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"

    # Status checking
    status_resp = client.get("/reports/status")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["status"] == "completed"
    assert status_body["result"]["total_evaluated"] == 0
    assert status_body["result"]["evaluated"] == []
