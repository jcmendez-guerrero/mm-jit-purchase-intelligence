import os

import uvicorn

from . import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8090")))  # noqa: S104
