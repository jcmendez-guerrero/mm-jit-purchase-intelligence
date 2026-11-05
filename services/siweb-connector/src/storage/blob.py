"""Blob storage for raw payloads: local directory (tests, Compose) and Azure Blob (production)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit


def blob_name(uri: str, container: str) -> str:
    """Blob name inside the container from a blob URL (the name may itself start with the container's name)."""
    path = urlsplit(uri).path
    marker = f"/{container}/"
    return path[path.index(marker) + len(marker):]


class BlobStore(Protocol):
    def put(self, name: str, data: bytes, expires_at: datetime) -> str: ...
    def get(self, uri: str) -> bytes: ...
    def delete(self, uri: str) -> None: ...  # a missing blob is not an error
    def exists(self, uri: str) -> bool: ...


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def put(self, name: str, data: bytes, expires_at: datetime) -> str:
        path = (self.root / name).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("blob name escapes the store")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_name(path.name + ".expires").write_text(expires_at.isoformat())
        return path.as_uri()

    def _path(self, uri: str) -> Path:
        return Path(uri.removeprefix("file://"))

    def get(self, uri: str) -> bytes:
        return self._path(uri).read_bytes()

    def delete(self, uri: str) -> None:
        p = self._path(uri)
        p.unlink(missing_ok=True)
        p.with_name(p.name + ".expires").unlink(missing_ok=True)

    def exists(self, uri: str) -> bool:
        return self._path(uri).exists()


class AzureBlobStore:
    """Writes with the connector's managed identity. Imported lazily; the Azure SDK is not needed locally."""

    def __init__(self, account_url: str, container: str) -> None:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]
        from azure.storage.blob import ContainerClient  # type: ignore[import-not-found]

        self._c = ContainerClient(account_url, container, credential=DefaultAzureCredential())

    @classmethod
    def from_connection_string(cls, conn: str, container: str) -> AzureBlobStore:
        """Azurite (local development and tests); production uses the managed identity constructor."""
        from azure.storage.blob import ContainerClient  # type: ignore[import-not-found]

        self = cls.__new__(cls)
        self._c = ContainerClient.from_connection_string(conn, container)
        try:
            self._c.create_container()
        except Exception:  # noqa: S110 - already exists
            pass
        return self

    def put(self, name: str, data: bytes, expires_at: datetime) -> str:
        blob = self._c.get_blob_client(name)
        blob.upload_blob(data, overwrite=True, metadata={"expires_at": expires_at.isoformat()})
        return str(blob.url)

    def get(self, uri: str) -> bytes:
        return bytes(self._c.get_blob_client(blob_name(uri, self._c.container_name)).download_blob().readall())

    def delete(self, uri: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError  # type: ignore[import-not-found]

        try:
            self._c.get_blob_client(blob_name(uri, self._c.container_name)).delete_blob()
        except ResourceNotFoundError:
            pass

    def exists(self, uri: str) -> bool:
        return bool(self._c.get_blob_client(blob_name(uri, self._c.container_name)).exists())
