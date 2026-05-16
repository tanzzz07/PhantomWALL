"""SQLAlchemy models for PhantomWall analytics."""

from app.models.analytics import Install, TrackerEventRecord
from app.models.base import Base

__all__ = ["Base", "Install", "TrackerEventRecord"]
