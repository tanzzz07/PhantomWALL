import sys
import os
import asyncio

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set dummy env variables
os.environ["PHANTOMWALL_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PHANTOMWALL_JWT_SECRET_KEY"] = "dummy-secret"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models import Base, Install
from app.services.analytics import AnalyticsService
from app.schemas.analytics import TrackEventIn


async def run_integration_test():
    print("Starting database integration test...")
    
    # 1. Initialize DB engine and session
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database tables created successfully.")
    
    # 2. Run Analytics Service tests
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
        print(f"Created test install: {install.display_name}")
        
        # Ingest tracker event (Analytics)
        event_1 = TrackEventIn(
            tracker_domain="google-analytics.com",
            url="https://www.google-analytics.com/g/collect?v=2&tid=UA-1234",
            page_origin="https://example.com",
            request_type="script",
            source="extension",
            blocked=True,
            third_party=True
        )
        stats_1, _ = await service.ingest_event(session, install, event_1)
        print("Ingested Event 1 (Analytics).")
        
        # Ingest tracker event (Advertising)
        event_2 = TrackEventIn(
            tracker_domain="doubleclick.net",
            url="https://ad.doubleclick.net/ddm/adj/N1234",
            page_origin="https://example.com",
            request_type="image",
            source="extension",
            blocked=True,
            third_party=True
        )
        stats_2, _ = await service.ingest_event(session, install, event_2)
        print("Ingested Event 2 (Advertising).")

        # Ingest safe event (Safe)
        event_3 = TrackEventIn(
            tracker_domain="mycorp.com",
            url="https://mycorp.com/api/userdata",
            page_origin="https://mycorp.com",
            request_type="xmlhttprequest",
            source="extension",
            blocked=False,
            third_party=False
        )
        stats_3, _ = await service.ingest_event(session, install, event_3)
        print("Ingested Event 3 (Safe).")

        # Verify classifications in recent events
        recent = stats_3.recent_events
        print("\nVerifying Ingested Event Classifications:")
        for idx, ev in enumerate(recent):
            print(f"[{idx+1}] Domain: {ev.tracker_domain} -> Classified: {ev.classification}")
            
        assert recent[0].classification == "Safe", "Event 3 should be classified as Safe"
        assert recent[1].classification == "Advertising", "Event 2 should be classified as Advertising"
        assert recent[2].classification == "Analytics", "Event 1 should be classified as Analytics"
        
        # Verify classification breakdown in stats
        breakdown = stats_3.classification_breakdown
        print("\nVerifying Classification Breakdown:")
        for entry in breakdown:
            print(f"- {entry.domain}: {entry.count}")
            
        categories = {entry.domain: entry.count for entry in breakdown}
        assert categories.get("Safe") == 1
        assert categories.get("Advertising") == 1
        assert categories.get("Analytics") == 1
        
    print("\nDatabase integration test PASSED successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_integration_test())
