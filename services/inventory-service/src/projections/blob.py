"""Read-only access to the connector's raw payloads (the envelope carries the URI and checksum)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class BlobReader(Protocol):
    def get(self, uri: str) -> bytes: ...


class LocalBlobReader:
    def get(self, uri: str) -> bytes:
        return Path(uri.removeprefix("file://")).read_bytes()


class AzureBlobReader:
    """Reads with inventory-service's managed identity (Storage Blob Data Reader on the raw container)."""

    def __init__(self, account_url: str, container: str) -> None:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]
        from azure.storage.blob import ContainerClient  # type: ignore[import-not-found]

        self._c = ContainerClient(account_url, container, credential=DefaultAzureCredential())

    def get(self, uri: str) -> bytes:
        name = uri.rsplit(f"/{self._c.container_name}/", 1)[-1]
        return bytes(self._c.get_blob_client(name).download_blob().readall())
