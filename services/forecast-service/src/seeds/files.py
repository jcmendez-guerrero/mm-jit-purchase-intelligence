"""Private local file store for seed originals (the Azure adapter implements the same put/get against the private, encrypted container)."""

from __future__ import annotations

from pathlib import Path


class LocalSeedStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def put(self, name: str, data: bytes) -> str:
        p = (self.root / name).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("blob name escapes the store")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()

    def get(self, ref: str) -> bytes:
        p = Path(ref.removeprefix("file://")).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("reference outside the store")
        return p.read_bytes()
