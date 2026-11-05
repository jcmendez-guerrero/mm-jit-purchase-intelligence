"""api-bff service entrypoint (T109, T110, T111, T137)."""

from fastapi import FastAPI
from mmi_common.service import create_service_app
from routes.admin_roles import router as admin_roles_router
from routes.api import router as api_router

# In api-bff, user session cookies are used for the frontend API.
# Service skeleton provides /healthz, /readyz.
app: FastAPI = create_service_app("api-bff", validator=lambda: None)

# Mount frontend-facing endpoints under /api per bff-api.openapi.yaml
app.include_router(api_router, prefix="/api")
app.include_router(admin_roles_router, prefix="/api")
