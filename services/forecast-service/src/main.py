"""forecast-service entrypoint: health/auth wiring, the forecast read API and the seed-import API. The forecast itself runs in the worker."""

import os
from pathlib import Path

from api import build_router
from imports_api import build_router as build_imports_router
from mmi_common.service import create_service_app

app = create_service_app("forecast-service")
app.include_router(build_router(app))
app.include_router(build_imports_router(app))


def _wire() -> None:
    """Upstreams for the import wizard (known variants, dry-run) and for re-forecast on request; absent in unit tests, which set their own."""
    if not (os.environ.get("MMI_DATABASE_URL") and os.environ.get("MMI_INVENTORY_URL")):
        return
    from mmi_common.servicetoken import service_token
    from runs.sources import InventoryHttpSource, LocalBlobWriter

    token = os.environ.get("MMI_INVENTORY_TOKEN") or (lambda: service_token("api://mmi-inventory-service", "svc-forecast", ["viewer"]))
    app.state.series_source = InventoryHttpSource(os.environ["MMI_INVENTORY_URL"], token)
    app.state.blob_writer = LocalBlobWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-forecast")))  # noqa: S108 - local default only


app.router.on_startup.append(_wire)
