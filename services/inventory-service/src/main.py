"""inventory-service entrypoint: health/auth wiring plus the inventory API."""

from api.routes import build_router
from mmi_common.service import create_service_app

app = create_service_app("inventory-service")
app.include_router(build_router(app))
