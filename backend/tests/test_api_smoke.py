from fastapi.testclient import TestClient

from pharma_management.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "pharma-management-api"
    assert payload["version"]
    assert response.headers["X-Request-ID"]


def test_readiness_endpoint_uses_postgres() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "pharma-management-api",
        "database": "ok",
    }
    assert response.headers["X-Request-ID"]


def test_security_headers_are_present() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
