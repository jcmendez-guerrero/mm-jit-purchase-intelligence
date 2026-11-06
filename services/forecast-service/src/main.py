"""forecast-service entrypoint: health/auth wiring and the forecast read API. The forecast itself runs in the worker."""

from api import build_router
from imports_api import build_router as build_imports_router
from mmi_common.service import create_service_app

app = create_service_app("forecast-service")
app.include_router(build_router(app))
app.include_router(build_imports_router(app))
