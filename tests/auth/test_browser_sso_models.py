from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import BrowserSSOConfig, ExtractRule, ProviderDefinition


def test_auth_type_has_browser_sso():
    assert AuthType.BROWSER_SSO == "browser_sso"


def test_flow_type_has_browser_sso():
    assert FlowType.BROWSER_SSO == "browser_sso"


def test_extract_rule_field_aliases():
    rule = ExtractRule.model_validate({"from": "cookies", "as": "cookie", "match": "*"})
    assert rule.from_ == "cookies"
    assert rule.as_ == "cookie"
    assert rule.match == "*"
    assert rule.json_path is None


def test_extract_rule_localstorage():
    rule = ExtractRule.model_validate(
        {
            "from": "localStorage",
            "as": "token",
            "match": "localConfig_v2",
            "jsonPath": "teams.T123.token",
        }
    )
    assert rule.from_ == "localStorage"
    assert rule.json_path == "teams.T123.token"


def test_browser_sso_config_minimal():
    config = BrowserSSOConfig(
        entry_url="https://x.com/",
        domains=["x.com"],
        extract=[ExtractRule.model_validate({"from": "cookies", "as": "cookie", "match": "*"})],
    )
    assert config.entry_url == "https://x.com/"
    assert config.validate_url is None
    assert config.extra_headers == {}
    assert config.login_mode == "auto"
    assert config.network_proxy is None
    assert config.ttl is None


def test_browser_sso_config_full():
    config = BrowserSSOConfig(
        entry_url="https://x.com/",
        domains=["x.com", "twitter.com"],
        validate_url="https://x.com/i/api/2/notifications/all.json?count=1",
        extract=[
            ExtractRule.model_validate({"from": "cookies", "as": "cookie", "match": "*"}),
            ExtractRule.model_validate({"from": "cookies", "as": "ct0", "match": "ct0"}),
        ],
        extra_headers={"Cookie": "${cookie}", "x-csrf-token": "${ct0}"},
        ttl="30d",
        network_proxy="socks5://127.0.0.1:1080",
    )
    assert len(config.extract) == 2
    assert config.extra_headers["Cookie"] == "${cookie}"
    assert config.ttl == "30d"


def test_provider_definition_browser_sso_field():
    defn = ProviderDefinition.model_validate(
        {
            "schema_version": 1,
            "name": "x-browser",
            "display_name": "X Browser SSO",
            "auth_type": "browser_sso",
            "flow": "browser_sso",
            "browser_sso": {
                "entry_url": "https://x.com/",
                "domains": ["x.com"],
                "extract": [{"from": "cookies", "as": "cookie", "match": "*"}],
            },
        }
    )
    assert defn.auth_type == AuthType.BROWSER_SSO
    assert defn.flow == FlowType.BROWSER_SSO
    assert defn.browser_sso is not None
    assert defn.browser_sso.entry_url == "https://x.com/"


def test_connection_record_credentials_field():
    record = ConnectionRecord(
        provider="x-browser",
        identity="test-agent",
        connection_name="default",
        auth_type=AuthType.BROWSER_SSO,
        status=ConnectionStatus.CONNECTED,
        credentials={"cookie": "abc=123; def=456", "ct0": "xyz"},
    )
    assert record.credentials == {"cookie": "abc=123; def=456", "ct0": "xyz"}


def test_connection_record_credentials_defaults_none():
    record = ConnectionRecord(
        provider="github",
        identity="test-agent",
        connection_name="default",
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token="tok",
    )
    assert record.credentials is None
