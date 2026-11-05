"""Service-to-service and user token validation (managed-identity / Entra tokens, dev issuer).

Tokens are JWTs. In Azure the keys come from the issuer's JWKS; locally a dev issuer signs with
an RSA key generated at start-up. Validation always checks signature, issuer, audience, expiry
and (for services) required app roles.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]
    auth_time: datetime | None
    claims: dict[str, Any] = field(default_factory=dict, compare=False)

    def mfa_fresh(self, max_age: timedelta = timedelta(minutes=5), now: datetime | None = None) -> bool:
        if self.auth_time is None:
            return False
        return ((now or datetime.now(UTC)) - self.auth_time) <= max_age


class TokenValidator:
    def __init__(self, issuer: str, audience: str, key: Any, algorithms: Iterable[str] = ("RS256",)):
        self._issuer, self._audience, self._key = issuer, audience, key
        self._algs = list(algorithms)

    def validate(self, token: str, required_roles: Iterable[str] = ()) -> Principal:
        try:
            claims = jwt.decode(
                token, self._key, algorithms=self._algs, audience=self._audience, issuer=self._issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError(f"invalid token: {exc.__class__.__name__}") from exc
        roles = frozenset(claims.get("roles", []))
        missing = set(required_roles) - roles
        if missing:
            raise AuthError("missing required role", status=403)
        auth_time = claims.get("auth_time")
        return Principal(
            subject=claims["sub"], roles=roles,
            auth_time=datetime.fromtimestamp(auth_time, UTC) if auth_time else None, claims=claims,
        )


class DevIssuer:
    """Local-only token issuer for tests and Compose. Never deployed."""

    def __init__(self, issuer: str = "http://dev-issuer.local"):
        self.issuer = issuer
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    @property
    def public_key(self) -> Any:
        return self._private.public_key()

    @property
    def public_pem(self) -> str:
        return self.public_key.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def issue(
        self, subject: str, audience: str, roles: Iterable[str] = (), ttl: timedelta = timedelta(minutes=30),
        auth_time: datetime | None = None, now: datetime | None = None,
    ) -> str:
        now = now or datetime.now(UTC)
        claims: dict[str, Any] = {
            "iss": self.issuer, "aud": audience, "sub": subject, "roles": list(roles),
            "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp()),
            "auth_time": int((auth_time or now).timestamp()),
        }
        return jwt.encode(claims, self._private, algorithm="RS256")


def bearer_token(authorization_header: str | None) -> str:
    if not authorization_header or not authorization_header.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    return authorization_header.split(" ", 1)[1].strip()
