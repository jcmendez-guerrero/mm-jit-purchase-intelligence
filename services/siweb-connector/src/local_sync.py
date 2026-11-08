"""T104: local-only trigger for the collection job (specs/004-local-test-data-suppliers, contracts/local-loader.md).

The connector has no other way to be started from outside, so the local export loader (command and screen) needs this one.
It exists only when ``MMI_LOCAL_LOADER=1`` and the environment is not production or staging, requires the ``local-loader`` role,
and runs only against the Siweb mock: any other host is refused, so the real ERP cannot be reached through this path.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool

LOCAL_HOSTS = {"siweb-mock", "localhost", "127.0.0.1", "::1"}


def enabled(env: Mapping[str, str]) -> bool:
    return env.get("MMI_LOCAL_LOADER") == "1" and env.get("MMI_ENV", "") not in {"prod", "staging"}


def _mark_default(environ: Mapping[str, str]) -> None:
    """Leave the marker that stops a later sync against the real ERP (FR-038). Skipped when there is no database configured."""
    url = environ.get("MMI_DATABASE_URL")
    if not url:
        return
    from mixing_guard import mark_local_data
    from sqlalchemy import create_engine

    mark_local_data(create_engine(url))


def register(app: FastAPI, runner: Callable[..., int] | None = None, env: Mapping[str, str] | None = None,
             marker: Callable[[Mapping[str, str]], None] | None = None) -> None:
    environ = os.environ if env is None else env
    if not enabled(environ):
        return
    require: Callable[..., Any] = app.state.require_roles

    @app.post("/internal/local-sync")
    async def local_sync(_p: Any = Depends(require("local-loader"))) -> dict[str, Any]:
        host = (urlsplit(environ.get("MMI_SIWEB_BASE_URL", "")).hostname or "").lower()
        if host not in LOCAL_HOSTS:
            raise HTTPException(403, detail="local sync runs only against the Siweb mock")
        if runner is None:
            from job import KINDS, run  # imported only when the route is called
            fn: Callable[..., int] = run
            kinds = list(KINDS)
        else:
            fn, kinds = runner, ["warehouses", "products", "variants", "movements", "lots", "supplier_costs"]
        await run_in_threadpool(marker or _mark_default, environ)
        code = await run_in_threadpool(fn, kinds, enforce_window=False)
        return {"ok": code == 0, "exit_code": code}
