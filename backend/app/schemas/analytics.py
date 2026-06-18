from datetime import datetime, timezone
from pydantic import BaseModel, Field

class TrackEventIn(BaseModel):
    # New MV3 telemetry schema fields
    timestamp: datetime | None = None
    url: str
    domain: str | None = None
    request_type: str | None = None
    blocked: bool = True
    action: str | None = None
    tab_url: str | None = None
    referrer: str | None = None
    third_party: bool = True

    # Legacy telemetry compatibility fields
    tracker_domain: str | None = None
    page_origin: str | None = None
    source: str = "extension"
    occurred_at: datetime | None = None


class BlockedRequestSchema(BaseModel):
    id: int
    timestamp: datetime
    full_url: str
    domain: str
    request_type: str
    blocked: bool
    action: str
    classification: str
    confidence: float
    risk_score: int
    third_party: bool
    tab_url: str | None = None
    referrer: str | None = None
    top_features: list[str] | None = None
    explanation: str | None = None


class HistoryResponse(BaseModel):
    items: list[BlockedRequestSchema]
    total: int
    page: int
    limit: int
    pages: int


class HistoryStatsResponse(BaseModel):
    total_requests: int
    blocked_count: int
    observed_count: int
    average_risk_score: float
    blocked_scripts: int
    analytics: int
    advertising: int
    fingerprinting: int
    suspicious: int
    over_time: list[dict]
    request_types: list[dict]
    risk_distribution: list[dict]


class TopDomainReputationSchema(BaseModel):
    domain: str
    classification: str
    times_seen: int
    times_blocked: int
    average_risk_score: float
    last_seen: datetime


class DomainReputationSchema(BaseModel):
    id: int
    domain: str
    times_seen: int
    times_blocked: int
    average_risk_score: float
    classification: str
    first_seen: datetime
    last_seen: datetime


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
    classification: str | None = "Safe"
    occurred_at: datetime


class StatsResponse(BaseModel):
    blocked_tracker_count: int
    total_events: int
    unique_tracker_count: int
    unique_install_count: int
    top_tracker_domains: list[DomainCount]
    request_type_breakdown: list[DomainCount]
    classification_breakdown: list[DomainCount]
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


class BlockedScriptRecord(BaseModel):
    occurred_at: datetime
    page_origin: str | None
    url: str
    classification: str | None
    install_name: str | None


