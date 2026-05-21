import importlib.resources
import json

from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import ProviderDefinition


def test_x_browser_json_loads_as_valid_provider():
    files = importlib.resources.files("authsome.auth.bundled_providers")
    provider_file = files / "x-browser.json"
    with provider_file.open("r") as f:
        data = json.load(f)
    defn = ProviderDefinition.model_validate(data)
    assert defn.name == "x-browser"
    assert defn.auth_type == AuthType.BROWSER_SSO
    assert defn.flow == FlowType.BROWSER_SSO
    assert defn.browser_sso is not None
    assert defn.browser_sso.entry_url == "https://x.com/"
    assert "x.com" in defn.browser_sso.domains
    assert defn.browser_sso.validate_url is not None
    assert len(defn.browser_sso.extract) >= 2
    assert "Cookie" in defn.browser_sso.extra_headers
    assert "x-csrf-token" in defn.browser_sso.extra_headers


def test_x_browser_loads_via_auth_service_bundled():
    """x-browser appears in the bundled providers loaded by AuthService."""
    from unittest.mock import MagicMock

    from authsome.server.credential_service import AuthService
    from authsome.vault import Vault

    vault = MagicMock(spec=Vault)
    svc = AuthService(vault=vault, identity="agent", principal_id="default", vault_id="default")
    assert "x-browser" in svc._bundled
