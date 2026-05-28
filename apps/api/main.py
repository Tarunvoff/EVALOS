from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    host = os.getenv("EVALOS_API_HOST", "127.0.0.1")
    port = int(os.getenv("EVALOS_API_PORT", "8000"))
    uvicorn.run("evalos.api.app:app", host=host, port=port, reload=True)
