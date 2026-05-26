from authsome.auth.sessions import AuthSession
from authsome.server.schemas import BrowserAction, NextAction


def test_browser_action_schema():
    action = BrowserAction(
        entry_url="https://x.com/",
        domains=["x.com"],
        validate_url="https://x.com/i/api/2/notifications/all.json",
        extract=[{"from": "cookies", "as": "cookie", "match": "*"}],
    )
    assert action.type == "browser"
    assert action.entry_url == "https://x.com/"


def test_next_action_discriminator_browser():
    """BrowserAction can be used as NextAction via discriminator."""
    from pydantic import TypeAdapter

    ta = TypeAdapter(NextAction)
    raw = {"type": "browser", "entry_url": "https://x.com/", "domains": ["x.com"], "extract": []}
    result = ta.validate_python(raw)
    assert isinstance(result, BrowserAction)


def test_session_response_returns_browser_action():
    """_session_response builds BrowserAction when flow_type is browser."""
    from authsome.server.routes.auth import _session_response

    session = AuthSession(
        session_id="sess_abc",
        provider="x-browser",
        identity="agent",
        connection_name="default",
        flow_type="browser",
        state="waiting_for_user",
    )
    session.payload["entry_url"] = "https://x.com/"
    session.payload["domains"] = ["x.com"]
    session.payload["validate_url"] = "https://x.com/i/api/2/notifications/all.json"
    session.payload["extract"] = [{"from": "cookies", "as": "cookie", "match": "*"}]
    session.payload["extra_headers"] = {"Cookie": "${cookie}", "x-csrf-token": "${ct0}"}

    response = _session_response(session, "http://localhost:7998")
    assert isinstance(response.next_action, BrowserAction)
    assert response.next_action.type == "browser"
    assert response.next_action.entry_url == "https://x.com/"
    assert response.next_action.extra_headers == {"Cookie": "${cookie}", "x-csrf-token": "${ct0}"}


def test_session_response_no_browser_when_completed():
    """Completed browser sessions return NoneAction, not BrowserAction."""
    from authsome.auth.sessions import AuthSessionStatus
    from authsome.server.routes.auth import _session_response

    session = AuthSession(
        session_id="sess_done",
        provider="x-browser",
        identity="agent",
        connection_name="default",
        flow_type="browser",
        state=AuthSessionStatus.COMPLETED,
    )
    session.payload["entry_url"] = "https://x.com/"
    session.payload["domains"] = ["x.com"]

    response = _session_response(session, "http://localhost:7998")
    assert response.next_action.type == "none"
