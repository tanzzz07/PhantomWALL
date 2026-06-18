import sys
import os
import asyncio
from datetime import datetime, timedelta, timezone

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set dummy env variables
os.environ["PHANTOMWALL_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PHANTOMWALL_JWT_SECRET_KEY"] = "dummy-secret-key-12345678901234567890"

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from app.models import Base, Install, BlockedRequest, DomainReputation
from app.services.analytics import AnalyticsService
from app.schemas.analytics import TrackEventIn
from app.services.explanation_service import ExplanationService
from app.services.retention import run_retention_cleanup


@pytest.mark.anyio
async def test_telemetry_ingestion_and_persistence():
    # 1. Initialize in-memory SQLite DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        service = AnalyticsService(max_recent_events=10)

        # Create a test install
        install = Install(
            id="test-install-uuid",
            display_name="Test Browser",
            token_hash="dummy-token-hash",
            is_active=True
        )
        session.add(install)
        await session.commit()
        await session.refresh(install)

        # Ingest a blocked request (e.g. fingerprinting tracker)
        event_blocked = TrackEventIn(
            url="https://fingerprint.example.com/fp.js?id=123",
            domain="fingerprint.example.com",
            request_type="script",
            blocked=True,
            action="blocked",
            third_party=True,
            referrer="https://initiator.com",
            timestamp=datetime.now(timezone.utc)
        )

        stats_res, blocked_record = await service.ingest_event(session, install, event_blocked)

        # Assert BlockedRequest was correctly saved
        assert blocked_record is not None
        assert blocked_record.domain == "fingerprint.example.com"
        assert blocked_record.blocked is True
        assert blocked_record.action == "blocked"
        assert blocked_record.classification == "Fingerprinting"
        # Verify dynamic risk score is calculated correctly: weight (0.85) * confidence (1.0 fallback) * 100 = 85
        assert blocked_record.risk_score == 85
        assert blocked_record.referrer == "https://initiator.com"

        # Ingest an observed (allowed) request
        event_observed = TrackEventIn(
            url="https://safe.example.com/style.css",
            domain="safe.example.com",
            request_type="stylesheet",
            blocked=False,
            action="observed",
            third_party=False,
            referrer="https://initiator.com",
            timestamp=datetime.now(timezone.utc)
        )

        _, observed_record = await service.ingest_event(session, install, event_observed)

        # Assert Observed request was saved
        assert observed_record is not None
        assert observed_record.domain == "safe.example.com"
        assert observed_record.blocked is False
        assert observed_record.action == "observed"
        assert observed_record.classification == "Safe"
        # Dynamic risk score: weight (0.1) * confidence (1.0 fallback) * 100 = 10
        assert observed_record.risk_score == 10

    await engine.dispose()


@pytest.mark.anyio
async def test_domain_reputation_updates():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        service = AnalyticsService(max_recent_events=10)
        install = Install(id="test-install", display_name="Test Browser", token_hash="token", is_active=True)
        session.add(install)
        await session.commit()

        # Ingest same domain twice: first blocked, second observed
        event_1 = TrackEventIn(
            url="https://badtracker.com/pixel.gif",
            domain="badtracker.com",
            request_type="image",
            blocked=True,
            timestamp=datetime.now(timezone.utc)
        )
        await service.ingest_event(session, install, event_1)

        event_2 = TrackEventIn(
            url="https://badtracker.com/some-script.js",
            domain="badtracker.com",
            request_type="script",
            blocked=False,
            timestamp=datetime.now(timezone.utc)
        )
        await service.ingest_event(session, install, event_2)

        # Check reputation metrics
        rep = await service.get_reputation_by_domain(session, "badtracker.com")
        assert rep is not None
        assert rep.times_seen == 2
        assert rep.times_blocked == 1
        # average risk calculation: (event_1 risk: 60 + event_2 risk: 60) / 2 = 60
        # Wait, classification for Advertising uses weight 0.6, so score is 60.
        assert rep.average_risk_score == 60.0

    await engine.dispose()


def test_dynamic_risk_scoring_and_explanations():
    # Test heuristic fallback in ExplanationService
    raw_features = {
        "third_party_flag": 1,
        "fingerprinting_keyword_score": 1,
        "request_frequency": 5
    }
    
    top_feats, explanation = ExplanationService.generate_explanation(
        raw_features=raw_features,
        classification="Fingerprinting",
        confidence=0.98
    )

    assert "third_party_flag" in top_feats
    assert "fingerprinting_keyword_score" in top_feats
    assert "classified as Fingerprinting" in explanation
    assert "it originated from a third-party domain" in explanation


@pytest.mark.anyio
async def test_retention_policy_cleanup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Create one recent request (1 day ago) and one old request (35 days ago)
        now = datetime.now(timezone.utc)
        recent = BlockedRequest(
            timestamp=now - timedelta(days=1),
            full_url="https://example.com",
            domain="example.com",
            request_type="script",
            blocked=True,
            action="blocked",
            classification="Analytics",
            confidence=1.0,
            risk_score=40,
            third_party=True
        )
        old = BlockedRequest(
            timestamp=now - timedelta(days=35),
            full_url="https://oldtracker.com",
            domain="oldtracker.com",
            request_type="script",
            blocked=True,
            action="blocked",
            classification="Suspicious",
            confidence=1.0,
            risk_score=95,
            third_party=True
        )
        session.add_all([recent, old])
        await session.commit()

        # Check raw counts before cleanup
        count_before = (await session.execute(select(func.count(BlockedRequest.id)))).scalar()
        assert count_before == 2

        # Run cleanup
        cleanup_res = await run_retention_cleanup(engine)
        assert cleanup_res["status"] == "success"
        assert cleanup_res["deleted_count"] == 1

        # Check raw counts after cleanup
        count_after = (await session.execute(select(func.count(BlockedRequest.id)))).scalar()
        assert count_after == 1

    await engine.dispose()
