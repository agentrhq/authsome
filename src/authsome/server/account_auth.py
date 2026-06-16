"""Account authentication for browser UI sessions."""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from authsome.identity.principal import PrincipalRecord
from authsome.server.config import get_server_config
from authsome.server.ownership import ensure_principal_default_vault
from authsome.server.store.repositories import (
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)
from authsome.server.ui_sessions import UI_TOKEN_AUDIENCE, BrowserSession, UiSessionStore

__all__ = ["AccountAuthService", "UI_TOKEN_AUDIENCE"]


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
        self._verify_password(principal.password_hash, password, message="Invalid email or password")
        return self._sessions.create_browser_session(principal_id=principal.principal_id, email=principal.email)

    async def change_password(
        self,
        *,
        principal_id: str,
        current_password: str,
        new_password: str,
    ) -> PrincipalRecord:
        principal = await self._principals.get(principal_id)
        if principal is None or not principal.password_hash:
            raise ValueError("Invalid current password")
        self._verify_password(principal.password_hash, current_password, message="Invalid current password")
        self._validate_password(new_password)
        return await self._principals.update_password(principal_id, password_hash=self._hasher.hash(new_password))

    def _verify_password(self, password_hash: str, password: str, *, message: str) -> None:
        try:
            self._hasher.verify(password_hash, password)
        except (VerificationError, VerifyMismatchError) as exc:
            raise ValueError(message) from exc
        except ValueError as exc:
            raise ValueError(message) from exc

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email address is required")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        min_length = get_server_config().min_password_length
        if len(password) < min_length:
            raise ValueError(f"Password must be at least {min_length} characters")
