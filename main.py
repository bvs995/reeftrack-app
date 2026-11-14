"""
AquaPulse Root Entrypoint Shim.
Allows running `uvicorn main:app` or `uvicorn backend.main:app` from the project root.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

for p in [BASE_DIR, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.main import app

__all__ = ["app"]
