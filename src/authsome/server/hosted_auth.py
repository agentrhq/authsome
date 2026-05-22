"""Hosted account authentication for browser UI sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from authsome.server.ownership import ensure_principal_default_vault
from authsome.server.registries import (
    PrincipalRecord,
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)
from authsome.utils import utc_now

UI_TOKEN_AUDIENCE = "authsome-ui"


@dataclass(frozen=True)
class HostedAccountSession:
    """Authenticated hosted browser account session."""

    principal_id: str
    email: str
    token: str


class HostedAccountService:
    """Register and authenticate hosted accounts.

    In hosted mode, the hosted account is the principal.
    """

    def __init__(
        self,
        *,
        principals: PrincipalRegistry,
        vaults: VaultRegistry,
        bindings: PrincipalVaultBindingRegistry,
        jwt_secret: str,
    ) -> None:
        self._principals = principals
        self._vaults = vaults
        self._bindings = bindings
        self._jwt_secret = jwt_secret
        self._hasher = PasswordHasher()

    async def register(self, *, email: str, password: str) -> PrincipalRecord:
        normalized = self._normalize_email(email)
        self._validate_password(password)
        password_hash = self._hasher.hash(password)
        principal = await self._principals.get_by_email(normalized)
        if principal is None:
            principal = await self._principals.create_by_email(normalized, password_hash=password_hash)
        elif principal.password_hash is not None:
            raise ValueError(f"Hosted account '{normalized}' is already registered")
        else:
            principal = await self._principals.update_password(principal.principal_id, password_hash=password_hash)
        await ensure_principal_default_vault(
            principal_id=principal.principal_id,
            vaults=self._vaults,
            bindings=self._bindings,
        )
        return principal

    async def register_and_login(self, *, email: str, password: str) -> HostedAccountSession:
        record = await self.register(email=email, password=password)
        return HostedAccountSession(
            principal_id=record.principal_id,
            email=record.email,
            token=self.issue_token(principal_id=record.principal_id, email=record.email),
        )

    async def login(self, *, email: str, password: str) -> HostedAccountSession:
        principal = await self._principals.get_by_email(self._normalize_email(email))
        if principal is None or not principal.password_hash:
            raise ValueError("Invalid email or password")
        try:
            self._hasher.verify(principal.password_hash, password)
        except (VerificationError, VerifyMismatchError) as exc:
            raise ValueError("Invalid email or password") from exc
        return HostedAccountSession(
            principal_id=principal.principal_id,
            email=principal.email,
            token=self.issue_token(principal_id=principal.principal_id, email=principal.email),
        )

    def issue_token(self, *, principal_id: str, email: str) -> str:
        now = utc_now()
        payload = {
            "sub": principal_id,
            "email": self._normalize_email(email),
            "aud": UI_TOKEN_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        return jwt.encode(payload, self._jwt_secret, algorithm="HS256")

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email address is required")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
