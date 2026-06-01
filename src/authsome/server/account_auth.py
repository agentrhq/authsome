"""Account authentication for browser UI sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from authsome.identity.principal import PrincipalRecord
from authsome.server.ownership import ensure_principal_default_vault
from authsome.server.settings import get_settings
from authsome.server.store.repositories import (
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)

if TYPE_CHECKING:
    from authsome.server.ui_sessions import BrowserSession, UiSessionStore

UI_TOKEN_AUDIENCE = "authsome-ui"


class AccountAuthService:
    """Register and authenticate browser accounts.

    An account is represented by a Principal and can claim one or more identities.
    Session tokens are minted by the injected ``UiSessionStore``, the single
    authority for browser-session JWTs.
    """

    def __init__(
        self,
        *,
        principals: PrincipalRegistry,
        vaults: VaultRegistry,
        bindings: PrincipalVaultBindingRegistry,
        sessions: UiSessionStore,
    ) -> None:
        self._principals = principals
        self._vaults = vaults
        self._bindings = bindings
        self._sessions = sessions
        self._hasher = PasswordHasher()

    async def register(self, *, email: str, password: str) -> PrincipalRecord:
        normalized = self._normalize_email(email)
        self._validate_password(password)
        password_hash = self._hasher.hash(password)
        principal = await self._principals.get_by_email(normalized)
        if principal is None:
            principal = await self._principals.create_by_email(normalized, password_hash=password_hash)
        elif principal.password_hash is not None:
            raise ValueError(f"Account '{normalized}' is already registered")
        else:
            principal = await self._principals.update_password(principal.principal_id, password_hash=password_hash)
        await ensure_principal_default_vault(
            principal_id=principal.principal_id,
            vaults=self._vaults,
            bindings=self._bindings,
        )
        return principal

    async def register_and_login(self, *, email: str, password: str) -> BrowserSession:
        record = await self.register(email=email, password=password)
        return self._sessions.create_browser_session(principal_id=record.principal_id, email=record.email)

    async def login(self, *, email: str, password: str) -> BrowserSession:
        principal = await self._principals.get_by_email(self._normalize_email(email))
        if principal is None or not principal.password_hash:
            raise ValueError("Invalid email or password")
        try:
            self._hasher.verify(principal.password_hash, password)
        except (VerificationError, VerifyMismatchError) as exc:
            raise ValueError("Invalid email or password") from exc
        return self._sessions.create_browser_session(principal_id=principal.principal_id, email=principal.email)

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email address is required")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        min_length = get_settings().min_password_length
        if len(password) < min_length:
            raise ValueError(f"Password must be at least {min_length} characters")
