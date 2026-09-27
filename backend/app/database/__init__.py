"""Database boundary exports."""

from backend.app.database.repository import IncidentRepository, InMemoryIncidentRepository

__all__ = ["IncidentRepository", "InMemoryIncidentRepository"]
