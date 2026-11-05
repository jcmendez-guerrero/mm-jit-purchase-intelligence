# ruff: noqa: S603, S607, S104
"""Throwaway Azurite (Azure Storage emulator) for adapter tests. Needs Docker; uses the digest from the Compose file."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ACCOUNT = "devstoreaccount1"
KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="   # the published, public emulator key
ROOT = Path(__file__).resolve().parents[3]


def available() -> bool:
    return bool(os.environ.get("RUN_AZURITE") and shutil.which("docker"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def azurite() -> Iterator[str]:
    """Yields a connection string for a fresh emulator with queue and blob endpoints."""
    m = re.search(r"image:\s*(mcr\.microsoft\.com/azure-storage/azurite:[^\s]+)", (ROOT / "infra/compose.yaml").read_text())
    if not m:
        raise RuntimeError("compose must pin the azurite image")
    qp, bp, name = _free_port(), _free_port(), f"mmi-azurite-{os.getpid()}-{int(time.time())}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{qp}:10001", "-p", f"127.0.0.1:{bp}:10000", m.group(1),
                    "azurite", "--skipApiVersionCheck", "--queueHost", "0.0.0.0", "--blobHost", "0.0.0.0"], check=True, capture_output=True)
    try:
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", qp), timeout=1), socket.create_connection(("127.0.0.1", bp), timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Azurite did not start")
        time.sleep(1)
        yield (f"DefaultEndpointsProtocol=http;AccountName={ACCOUNT};AccountKey={KEY};"
               f"BlobEndpoint=http://127.0.0.1:{bp}/{ACCOUNT};QueueEndpoint=http://127.0.0.1:{qp}/{ACCOUNT};")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
