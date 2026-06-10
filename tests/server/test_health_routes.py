"""Tests for server health routes."""

from fastapi import status

from tests.server.helpers import create_server_test_client


def test_root_health_alias_matches_api_health(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        root = client.get("/health")
        api = client.get("/api/health")

    assert root.status_code == status.HTTP_200_OK
    assert root.json()["status"] == "ok"
    assert root.json()["version"] == api.json()["version"]


def test_api_health_route_is_registered_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        api_health_routes = [route for route in client.app.router.routes if getattr(route, "path", "") == "/api/health"]

    assert len(api_health_routes) == 1
