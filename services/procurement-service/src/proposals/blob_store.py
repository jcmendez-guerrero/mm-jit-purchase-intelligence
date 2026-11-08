"""Local file blob writer for event payloads (the Azure adapter implements the same ``put``)."""

from __future__ import annotations

import os
from pathlib import Path


class FileWriter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, name: str, data: bytes) -> str:
        root = os.path.realpath(self.root)
        target = os.path.realpath(os.path.join(root, name))
        if not target.startswith(root + os.sep):                  # the name must stay inside the store (also rejects absolute names and "..")
            raise ValueError("blob name escapes the store")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        return Path(target).as_uri()
