from __future__ import annotations

from fastapi.testclient import TestClient

from authsome.server.app import create_app


def test_app_lifespan_wires_store_repositories(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DATABASE_URL", raising=False)

    with TestClient(create_app()) as client:
        store = client.app.state.store
        assert store.backend == "sqlite"
        assert client.app.state.identity_registry is store.identity_registry
        assert client.app.state.vault_registry is store.vaults
        assert client.app.state.identity_claim_registry is store.identity_claims
        assert client.app.state.principal_vault_binding_registry is store.principal_vault_bindings
