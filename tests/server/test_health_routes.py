"""Tests for server health routes."""

from fastapi import status

from tests.server.helpers import create_server_test_client


def _registered_paths(routes, prefix: str = "") -> list[str]:  # noqa: ANN001
    paths: list[str] = []
    for route in routes:
        path = getattr(route, "path", "")
        full_path = f"{prefix.rstrip('/')}/{path.lstrip('/')}" if prefix else path
        paths.append(full_path)
        child_routes = getattr(route, "routes", None)
        if child_routes is not None:
            paths.extend(_registered_paths(child_routes, full_path))
    return paths


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
        api_health_routes = [path for path in _registered_paths(client.app.router.routes) if path == "/api/health"]

    assert len(api_health_routes) == 1
