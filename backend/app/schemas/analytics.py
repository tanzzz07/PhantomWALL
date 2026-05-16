from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TrackEventIn(BaseModel):
    tracker_domain: str
    url: str
    page_origin: str | None = None
    request_type: str | None = None
    source: str = "extension"
    blocked: bool = True
    third_party: bool = True
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DomainCount(BaseModel):
    domain: str
    count: int


class TrackerEvent(BaseModel):
    event_id: int | None = None
    install_id: str | None = None
    install_name: str | None = None
    tracker_domain: str
    url: str
    page_origin: str | None = None
    request_type: str | None = None
    source: str
    blocked: bool
    third_party: bool
    occurred_at: datetime


class StatsResponse(BaseModel):
    blocked_tracker_count: int
    total_events: int
    unique_tracker_count: int
    unique_install_count: int
    top_tracker_domains: list[DomainCount]
    request_type_breakdown: list[DomainCount]
    installs: list["InstallTraffic"]
    recent_events: list[TrackerEvent]
    service_status: str
    generated_at: datetime
    selected_install_id: str | None = None


class TrackEventResponse(BaseModel):
    status: str
    stats: StatsResponse


class InstallTraffic(BaseModel):
    install_id: str
    display_name: str
    event_count: int
    blocked_count: int
    last_seen_at: datetime | None = None


StatsResponse.model_rebuild()

