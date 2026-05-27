from __future__ import annotations

from fastapi.testclient import TestClient

from authsome.server.app import create_app


def test_health_includes_store_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DATABASE_URL", raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["store_backend"] == "sqlite"
