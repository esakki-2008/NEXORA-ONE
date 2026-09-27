"""Convenient import target for local ASGI runners."""

from backend.app.main import app, create_app

__all__ = ["app", "create_app"]
