"""T089: authenticated, audience-scoped identities for the loader (constitution Principle IV, FR-039).

Inbound: the loader app accepts only tokens issued for ``api://mmi-local-loader`` to the BFF or to the local command.
Outbound: the loader calls inventory-service and procurement-service with its own principal ``svc-local-loader``.
Local environment only: the dev issuer is the sole token source and the loader refuses to start outside ``MMI_ENV=dev``.
"""

from __future__ import annotations

import os

import httpx
from mmi_common.auth import AuthError, Principal, TokenValidator, bearer_token
from mmi_common.servicetoken import service_token

AUDIENCE = "api://mmi-local-loader"
ALLOWED_SUBJECTS = frozenset({"svc-api-bff", "svc-local-loader-cli"})
LOADER_SUBJECT = "svc-local-loader"


class LoaderAuth:
    def __init__(self, validator: TokenValidator) -> None:
        self._validator = validator

    def check(self, authorization_header: str | None) -> Principal:
        principal = self._validator.validate(bearer_token(authorization_header))
        if principal.subject not in ALLOWED_SUBJECTS:
            raise AuthError("caller is not allowed to use the loader", status=403)
        return principal


def validator_from_env() -> TokenValidator:
    if os.environ.get("MMI_ENV") != "dev":
        raise RuntimeError("the local loader only runs with MMI_ENV=dev")
    base = os.environ["MMI_DEV_ISSUER_URL"].rstrip("/")
    key = httpx.get(f"{base}/public-key", timeout=5).text
    return TokenValidator(os.environ.get("MMI_ISSUER", "http://dev-issuer.local"), AUDIENCE, key)


def loader_token(audience: str) -> str:
    """A token for the loader's own calls to platform services (cached for a few minutes, never logged)."""
    return service_token(audience, LOADER_SUBJECT, ["local-loader"])


def cli_token() -> str:
    """Token used by the local command to call the loader app or the connector trigger."""
    return service_token(AUDIENCE, "svc-local-loader-cli", ["local-loader"])
