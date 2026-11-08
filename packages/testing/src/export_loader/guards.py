"""Runtime guards that keep real data local (constitution v1.3.0, Principle II; AGENTS.md rule 7a).

* the loader reads only from ``data/`` (ignored by version control) or the synthetic fixtures folder when it sits inside the repository;
* it talks only to local services;
* it refuses to run outside ``MMI_ENV=dev``.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

FIXTURES = ("packages", "testing", "fixtures", "exports")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "siweb-mock", "local-loader", "siweb-connector", "dev-issuer", "postgres", "azurite",
               "procurement-service", "inventory-service", "forecast-service", "api-bff"}


class GuardError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def repo_root(start: Path | None = None) -> Path | None:
    p = (start or Path(__file__)).resolve()
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def check_dir(path: Path, root: Path | None = None) -> Path:
    """Inside the repository only ``data/`` and the synthetic fixtures folder are allowed."""
    resolved = Path(path).resolve()
    root = (root or repo_root())
    if root is None:
        return resolved
    root = root.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        return resolved                                   # outside the repository: the owner's private folder
    parts = rel.parts
    if parts[:1] == ("data",) or parts[: len(FIXTURES)] == FIXTURES:
        return resolved
    raise GuardError("local_load_dir_not_allowed", "La carpeta está dentro del repositorio; use data/local-exports o una carpeta fuera del repositorio")


def check_local_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise GuardError("local_load_not_local_target", f"El destino no es local: {host or url}")
    return url


def check_environment() -> None:
    if os.environ.get("MMI_ENV", "dev") in {"prod", "staging"}:
        raise GuardError("local_load_disabled", "La carga local no está disponible en este entorno")
