from fastapi import status

from tests.server.helpers import create_server_test_client


def test_browser_session_can_change_account_password(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        registered = client.post(
            "/api/auth/register",
            data={"email": "dev@example.com", "password": "password-1", "next": "/settings?tab=security"},
            follow_redirects=False,
        )
        response = client.post(
            "/api/auth/password",
            data={
                "current_password": "password-1",
                "new_password": "password-2",
                "next": "/settings?tab=security",
            },
            follow_redirects=False,
        )
        client.post("/api/logout", follow_redirects=False)
        old_login = client.post(
            "/api/auth/login",
            data={"email": "dev@example.com", "password": "password-1", "next": "/"},
            follow_redirects=False,
        )
        new_login = client.post(
            "/api/auth/login",
            data={"email": "dev@example.com", "password": "password-2", "next": "/"},
            follow_redirects=False,
        )

    assert registered.status_code == status.HTTP_303_SEE_OTHER
    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/settings?tab=security&password_changed=1"
    assert old_login.headers["location"] == "/login?next=%2F&error=Invalid+email+or+password&tab=login"
    assert new_login.status_code == status.HTTP_303_SEE_OTHER
