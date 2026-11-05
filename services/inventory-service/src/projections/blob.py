"""Read-only access to the connector's raw payloads (the envelope carries the URI and checksum)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit


def blob_name(uri: str, container: str) -> str:
    """Blob name inside the container from a blob URL (the name may itself start with the container's name)."""
    path = urlsplit(uri).path
    marker = f"/{container}/"
    return path[path.index(marker) + len(marker):]


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

    @classmethod
    def from_connection_string(cls, conn: str, container: str) -> AzureBlobReader:
        from azure.storage.blob import ContainerClient  # type: ignore[import-not-found]

        self = cls.__new__(cls)
        self._c = ContainerClient.from_connection_string(conn, container)
        return self

    def get(self, uri: str) -> bytes:
        name = blob_name(uri, self._c.container_name)
        return bytes(self._c.get_blob_client(name).download_blob().readall())
