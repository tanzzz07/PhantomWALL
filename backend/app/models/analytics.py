from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    installs: Mapped[list["Install"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Install(Base):
    __tablename__ = "installs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    extension_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    browser_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped["User | None"] = relationship(back_populates="installs")
    events: Mapped[list["TrackerEventRecord"]] = relationship(
        back_populates="install",
        cascade="all, delete-orphan",
    )


class TrackerEventRecord(Base):
    __tablename__ = "tracker_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    install_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracker_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="extension")
    blocked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    third_party: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    install: Mapped[Install] = relationship(back_populates="events")

