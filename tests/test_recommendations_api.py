from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _headers(partner_id="partner_capped", agent_id="agent-test"):
    return {"x-partner-id": partner_id, "x-agent-id": agent_id}


def test_happy_path_returns_recommendations():
    resp = client.post("/recommendations", json={"member_id": "M-silver-capped"}, headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["partner_id"] == "partner_capped"
    assert len(body["recommendations"]) <= 3
    assert "rule_metadata" in body


def test_unknown_member_returns_404_error_shape():
    resp = client.post("/recommendations", json={"member_id": "M-nope"}, headers=_headers())
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "UNKNOWN_MEMBER"
    assert "request_id" in body


def test_cross_partner_returns_403():
    resp = client.post(
        "/recommendations",
        json={"member_id": "M-plat-nocruise"},
        headers=_headers(partner_id="partner_capped"),
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "AUTHORIZATION_DENIED"


def test_missing_partner_config_returns_404():
    resp = client.post(
        "/recommendations",
        json={"member_id": "M-orphan"},
        headers=_headers(partner_id="partner_missing"),
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "MISSING_PARTNER_CONFIG"


def test_missing_headers_returns_422_error_shape():
    resp = client.post("/recommendations", json={"member_id": "M-silver-capped"})
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "VALIDATION_ERROR"


def test_cruise_never_appears_via_rest_for_excluding_partner():
    resp = client.post(
        "/recommendations",
        json={"member_id": "M-plat-nocruise"},
        headers=_headers(partner_id="partner_no_cruise"),
    )
    assert resp.status_code == 200
    cats = [r["category"] for r in resp.json()["recommendations"]]
    assert "Cruise" not in cats
