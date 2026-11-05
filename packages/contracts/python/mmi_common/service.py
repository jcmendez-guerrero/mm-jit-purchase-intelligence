"""FastAPI service skeleton: health endpoints and an authentication/role dependency.

Key material comes from the environment:
- ``MMI_DEV_ISSUER_URL``: local dev issuer (Compose only, ``MMI_ENV=dev``) serving ``/public-key``;
- ``MMI_JWKS_URL``: the identity provider's JWKS in Azure (managed identities / Entra ID).
Audience defaults to ``api://mmi-<service>``; the issuer to ``MMI_ISSUER``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from .auth import AuthError, Principal, TokenValidator, bearer_token
from .logging import configure_logging
from .time import set_correlation_id


def _fetch_public_key(url: str) -> str:
    """Fetch the PEM public key from dev-issuer, handling both plain-text and JSON responses."""
    resp = httpx.get(f"{url}/public-key", timeout=5)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        # FastAPI may JSON-encode the PEM string; unwrap it.
        return resp.json()
    pem = resp.text
    # Guard against leftover JSON quotes (older images).
    if pem.startswith('"') and pem.endswith('"'):
        import json
        pem = json.loads(pem)
    return pem


def validator_from_env(audience: str) -> TokenValidator:
    issuer = os.environ.get("MMI_ISSUER", "http://dev-issuer.local")
    if url := os.environ.get("MMI_DEV_ISSUER_URL"):
        if os.environ.get("MMI_ENV") != "dev":
            raise RuntimeError("the dev issuer is only allowed with MMI_ENV=dev")
        pem = _fetch_public_key(url)
        return TokenValidator(issuer, audience, pem)
    if jwks := os.environ.get("MMI_JWKS_URL"):
        import jwt

        client = jwt.PyJWKClient(jwks)

        class _Jwks(TokenValidator):
            def validate(self, token: str, required_roles: Any = ()) -> Principal:
                self._key = client.get_signing_key_from_jwt(token).key
                return super().validate(token, required_roles)

        return _Jwks(issuer, audience, None)
    raise RuntimeError("configure MMI_DEV_ISSUER_URL (dev) or MMI_JWKS_URL")


def create_service_app(
    name: str,
    validator: TokenValidator | Callable[[], TokenValidator] | None = None,
    readiness: list[Callable[[], bool]] | None = None,
) -> FastAPI:
    configure_logging()
    app = FastAPI(title=name)
    audience = os.environ.get("MMI_AUDIENCE", f"api://mmi-{name}")
    holder: dict[str, TokenValidator] = {}

    def get_validator() -> TokenValidator:
        if "v" not in holder:
            v = validator() if callable(validator) else validator
            holder["v"] = v or validator_from_env(audience)
        return holder["v"]

    def require_roles(*roles: str) -> Callable[..., Principal]:
        def dep(authorization: str | None = Header(default=None), x_correlation_id: str | None = Header(default=None)) -> Principal:
            set_correlation_id(x_correlation_id)
            try:
                token = bearer_token(authorization)  # reject anonymous calls before any key lookup
                return get_validator().validate(token, roles)
            except AuthError as exc:
                raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
            except RuntimeError as exc:  # identity configuration missing: fail closed
                raise HTTPException(status_code=503, detail="authentication not configured") from exc

        return dep

    app.state.require_roles = require_roles

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": name}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        if readiness and not all(check() for check in readiness):
            raise HTTPException(status_code=503, detail="not ready")
        return {"status": "ready", "service": name}

    @app.get("/whoami")
    def whoami(principal: Principal = Depends(require_roles())) -> dict[str, Any]:
        return {"subject": principal.subject, "roles": sorted(principal.roles)}

    return app
