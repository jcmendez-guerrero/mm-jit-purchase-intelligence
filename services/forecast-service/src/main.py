"""forecast-service entrypoint: health/auth wiring. The forecast itself runs as a job (python -m job)."""

from mmi_common.service import create_service_app

app = create_service_app("forecast-service")
