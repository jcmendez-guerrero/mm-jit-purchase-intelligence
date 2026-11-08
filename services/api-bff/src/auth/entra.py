"""Microsoft Entra ID sign-in for humans (research R12): OIDC authorization-code flow with PKCE, run by the BFF.

The browser never holds a token. The BFF redirects to Entra, exchanges the code, validates the id_token (signature
against the tenant JWKS, issuer, audience, nonce, expiry) and issues the usual signed cookie session. Roles come from
the app roles in the token; multi-factor time comes from ``auth_time`` when Entra supplies it, otherwise from ``iat``
when ``amr`` shows MFA was used, otherwise the session starts with no fresh MFA (step-up then refuses approvals).

Configuration (environment, never committed): MMI_ENTRA_TENANT_ID, MMI_ENTRA_CLIENT_ID, MMI_ENTRA_CLIENT_SECRET
(Key Vault reference in Azure), MMI_ENTRA_REDIRECT_URI (the public https URL of /api/auth/callback). Optional:
MMI_ENTRA_AUTHORITY (default https://login.microsoftonline.com), MMI_ENTRA_JWKS_URL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from auth.session import get_secret_key

VALID_ROLES = ("viewer", "buyer", "approver", "admin")
STATE_COOKIE = "mmi_oidc"
STATE_TTL_SECONDS = 600


class EntraError(Exception):
    """A sign-in step failed; ``code`` is a stable machine key (never the provider's raw message)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EntraConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    redirect_uri: str
    authority: str = "https://login.microsoftonline.com"

    @property
    def issuer(self) -> str:
        return f"{self.authority}/{self.tenant_id}/v2.0"

    @property
    def authorize_url(self) -> str:
        return f"{self.authority}/{self.tenant_id}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.authority}/{self.tenant_id}/oauth2/v2.0/token"

    @property
    def jwks_url(self) -> str:
        return os.environ.get("MMI_ENTRA_JWKS_URL") or f"{self.authority}/{self.tenant_id}/discovery/v2.0/keys"


def entra_config() -> EntraConfig | None:
    env = os.environ
    values = [env.get(k, "") for k in ("MMI_ENTRA_TENANT_ID", "MMI_ENTRA_CLIENT_ID", "MMI_ENTRA_CLIENT_SECRET", "MMI_ENTRA_REDIRECT_URI")]
    if not all(values):
        return None
    return EntraConfig(*values, authority=env.get("MMI_ENTRA_AUTHORITY", "https://login.microsoftonline.com").rstrip("/"))


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def pkce_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode()).digest())


def _sign(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{body}.{hmac.new(get_secret_key(), body.encode(), hashlib.sha256).hexdigest()}"


def _unsign(value: str) -> dict[str, Any] | None:
    try:
        body, sig = value.split(".", 1)
        if not hmac.compare_digest(sig, hmac.new(get_secret_key(), body.encode(), hashlib.sha256).hexdigest()):
            return None
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
        return data if data.get("exp", 0) >= int(datetime.now(UTC).timestamp()) else None
    except Exception:
        return None


def begin(cfg: EntraConfig) -> tuple[str, str]:
    """Return (authorize URL, signed state cookie value). State, nonce and PKCE verifier live only in the cookie."""
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    cookie = _sign({"s": state, "n": nonce, "v": verifier, "exp": int(datetime.now(UTC).timestamp()) + STATE_TTL_SECONDS})
    query = urlencode({
        "client_id": cfg.client_id, "response_type": "code", "redirect_uri": cfg.redirect_uri, "response_mode": "query",
        "scope": "openid profile email", "state": state, "nonce": nonce,
        "code_challenge": pkce_challenge(verifier), "code_challenge_method": "S256",
    })
    return f"{cfg.authorize_url}?{query}", cookie


def exchange_code(cfg: EntraConfig, code: str, verifier: str) -> str:
    """Swap the authorization code for the id_token (patched in tests; the only outbound call besides the JWKS)."""
    resp = httpx.post(cfg.token_url, timeout=10, data={
        "client_id": cfg.client_id, "client_secret": cfg.client_secret, "grant_type": "authorization_code", "code": code,
        "redirect_uri": cfg.redirect_uri, "code_verifier": verifier, "scope": "openid profile email",
    })
    if resp.status_code != 200 or "id_token" not in resp.json():
        raise EntraError("token_exchange_failed")
    return str(resp.json()["id_token"])


def signing_key(cfg: EntraConfig, token: str) -> Any:
    """Look up the tenant's signing key for this token (patched in tests)."""
    return jwt.PyJWKClient(cfg.jwks_url).get_signing_key_from_jwt(token).key


def validate_id_token(cfg: EntraConfig, token: str, nonce: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, signing_key(cfg, token), algorithms=["RS256"], audience=cfg.client_id, issuer=cfg.issuer,
                            options={"require": ["exp", "iat", "iss", "aud"]})
    except Exception as exc:
        raise EntraError("token_invalid") from exc
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise EntraError("nonce_mismatch")
    return claims


def identity_from_claims(claims: dict[str, Any]) -> tuple[str, str, list[str], datetime | None]:
    """(user id, e-mail, app roles, MFA time). The object id is the stable key; unknown role names are ignored."""
    user_id = str(claims.get("oid") or claims.get("sub") or "")
    if not user_id:
        raise EntraError("token_invalid")
    email = str(claims.get("preferred_username") or claims.get("email") or "")
    roles = [r for r in VALID_ROLES if r in (claims.get("roles") or [])]
    mfa: datetime | None = None
    if claims.get("auth_time"):
        mfa = datetime.fromtimestamp(int(claims["auth_time"]), UTC)
    elif "mfa" in (claims.get("amr") or []):
        mfa = datetime.fromtimestamp(int(claims["iat"]), UTC)
    return user_id, email, roles, mfa


def complete(cfg: EntraConfig, state_cookie: str | None, state: str, code: str) -> tuple[str, str, list[str], datetime | None]:
    saved = _unsign(state_cookie or "")
    if not saved or not hmac.compare_digest(saved["s"], state):
        raise EntraError("state_mismatch")
    claims = validate_id_token(cfg, exchange_code(cfg, code, saved["v"]), saved["n"])
    return identity_from_claims(claims)
