"""Token providers for the reader identity. Tokens are never logged or stored."""

from __future__ import annotations

import os
from typing import Protocol


class TokenProvider(Protocol):
    def get_token(self) -> str: ...


class EnvTokenProvider:
    """Local stub: reads the token from an environment variable (dev and tests only)."""

    def __init__(self, var: str = "MMI_SIWEB_TOKEN") -> None:
        self._var = var

    def get_token(self) -> str:
        value = os.environ.get(self._var)
        if not value:
            raise RuntimeError(f"{self._var} is not set")
        return value


class StaticTokenProvider:
    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self) -> str:
        return self._token

    def __repr__(self) -> str:  # keep the secret out of logs and tracebacks
        return "StaticTokenProvider(token=***)"


class KeyVaultTokenProvider:
    """Reads the secret with the reader's managed identity; the value is cached only in memory."""

    def __init__(self, vault_url: str, secret_name: str) -> None:
        self._vault_url, self._secret_name = vault_url, secret_name
        self._cached: str | None = None

    def get_token(self) -> str:
        if self._cached is None:
            from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]
            from azure.keyvault.secrets import SecretClient  # type: ignore[import-not-found]

            client = SecretClient(vault_url=self._vault_url, credential=DefaultAzureCredential())
            self._cached = client.get_secret(self._secret_name).value or ""
        return self._cached

    def invalidate(self) -> None:
        """Called after a 401 so the next call re-reads a rotated secret."""
        self._cached = None


def provider_from_env() -> TokenProvider:
    vault, name = os.environ.get("MMI_KEYVAULT_URL"), os.environ.get("MMI_SIWEB_SECRET_NAME")
    if vault and name:
        return KeyVaultTokenProvider(vault, name)
    return EnvTokenProvider()
