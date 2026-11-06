"""Local file blob writer for event payloads (the Azure adapter implements the same ``put``)."""

from __future__ import annotations

from pathlib import Path


class FileWriter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, name: str, data: bytes) -> str:
        p = (self.root / name).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("blob name escapes the store")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()
