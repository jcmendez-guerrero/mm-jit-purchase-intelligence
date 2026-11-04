"""procurement-service entrypoint: health/auth wiring plus the cost and terms API."""

from api.costs import build_router
from mmi_common.service import create_service_app

app = create_service_app("procurement-service")
app.include_router(build_router(app))
