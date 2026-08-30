"""Tests for the optional public-demo access gate."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.demo_access import DemoAccessMiddleware


def _client(access_key: str | None) -> TestClient:
    app = FastAPI()
    app.add_middleware(DemoAccessMiddleware, access_key=access_key)

    @app.get("/health/")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/example")
    async def example():
        return {"ok": True}

    return TestClient(app)


def test_guard_is_disabled_when_key_is_unset():
    response = _client(None).get("/api/example")
    assert response.status_code == 200


def test_health_remains_public_when_guard_is_enabled():
    response = _client("demo-secret").get("/health/")
    assert response.status_code == 200


def test_guard_rejects_missing_or_wrong_key():
    client = _client("demo-secret")
    assert client.get("/api/example").status_code == 403
    assert client.get("/api/example", headers={"X-Demo-Key": "wrong"}).status_code == 403


def test_guard_accepts_matching_key():
    response = _client("demo-secret").get(
        "/api/example", headers={"X-Demo-Key": "demo-secret"}
    )
    assert response.status_code == 200
