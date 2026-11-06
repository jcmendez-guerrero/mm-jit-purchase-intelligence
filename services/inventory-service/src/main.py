"""inventory-service entrypoint: health/auth wiring plus the inventory API."""

import os
from pathlib import Path

from api.routes import build_router
from demand.publisher import LocalBlobWriter
from mmi_common.service import create_service_app

app = create_service_app("inventory-service")
app.include_router(build_router(app))
if os.environ.get("MMI_DATABASE_URL"):                  # rule changes announce themselves so the forecast is recomputed (T094)
    app.state.blob_writer = LocalBlobWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-inventory")))  # noqa: S108 - local default only
