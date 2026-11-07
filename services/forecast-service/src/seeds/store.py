"""Where uploaded seed originals are kept: a local folder (development, tests) or the private ``seed-quarantine`` Azure container.

Both implement ``put(name, data) -> reference`` and ``get(reference) -> bytes``. Production never falls back to a local folder.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from seeds.files import LocalSeedStore

CONTAINER = "seed-quarantine"


class AzureSeedStore:
    """The container is private and encrypted by the service; access is by the forecast identity only (Storage Blob Data Contributor)."""

    def __init__(self, container_client: Any) -> None:
        self._c = container_client

    @classmethod
    def from_account_url(cls, account_url: str, container: str = CONTAINER) -> AzureSeedStore:
        from azure.identity import DefaultAzureCredential  # lazy: the Azure SDK is not needed locally
        from azure.storage.blob import ContainerClient

        return cls(ContainerClient(account_url, container, credential=DefaultAzureCredential()))

    @classmethod
    def from_connection_string(cls, conn: str, container: str = CONTAINER) -> AzureSeedStore:
        """Azurite (local development and tests only)."""
        from azure.storage.blob import ContainerClient

        c = ContainerClient.from_connection_string(conn, container)
        try:
            c.create_container()
        except Exception:  # noqa: S110 - already exists
            pass
        return cls(c)

    @staticmethod
    def _safe(name: str) -> str:
        parts = name.split("/")
        if not name or name.startswith("/") or "\\" in name or any(p in ("", ".", "..") for p in parts):
            raise ValueError("blob name escapes the container")
        return name

    def put(self, name: str, data: bytes) -> str:
        blob = self._c.get_blob_client(self._safe(name))
        blob.upload_blob(data, overwrite=True)
        return str(blob.url)

    def get(self, ref: str) -> bytes:
        marker = f"/{self._c.container_name}/"
        path = urlsplit(ref).path
        if marker not in path:
            raise ValueError("reference outside the container")
        name = self._safe(path[path.index(marker) + len(marker):])
        return bytes(self._c.get_blob_client(name).download_blob().readall())


def make_seed_store() -> LocalSeedStore | AzureSeedStore:
    """Azure when configured (managed identity, or a connection string for Azurite); a local folder only outside production."""
    account = os.environ.get("MMI_SEED_ACCOUNT_URL")
    if account:
        return AzureSeedStore.from_account_url(account, os.environ.get("MMI_SEED_CONTAINER", CONTAINER))
    conn = os.environ.get("MMI_SEED_CONNECTION")
    if conn:
        return AzureSeedStore.from_connection_string(conn, os.environ.get("MMI_SEED_CONTAINER", CONTAINER))
    if os.environ.get("MMI_ENV", "dev") == "prod":
        raise RuntimeError("seed storage is not configured: set MMI_SEED_ACCOUNT_URL")
    return LocalSeedStore(Path(os.environ.get("MMI_SEED_ROOT", "/tmp/mmi-forecast-seeds")))  # noqa: S108 - local default only
