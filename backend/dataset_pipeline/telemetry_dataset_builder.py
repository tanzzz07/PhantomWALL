import os
import sys
import json
import random
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Resolve path for backend imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TELEMETRY_DIR = Path(__file__).resolve().parent.parent / "data" / "telemetry"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

IS_CI = os.environ.get("CI", "").lower() in ("true", "1", "yes")


def ensure_dirs():
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_db_telemetry() -> list[dict]:
    """Fetch real telemetry from the PostgreSQL/SQLite tracker_events table.

    All heavy imports (SQLAlchemy engine, models) are deferred to this function
    so they never execute in CI where no database is available.
    """
    logger.info("Attempting to query telemetry from database...")

    # Lazy imports — only executed when this function is actually called
    try:
        from app.core.config import get_settings
        from app.db import AsyncSessionFactory
        from app.models.analytics import TrackerEventRecord
        from sqlalchemy import select
    except Exception as e:
        logger.warning(f"Failed to import database modules: {e}. Returning empty.")
        return []

    try:
        async with AsyncSessionFactory() as session:
            stmt = select(TrackerEventRecord).order_by(TrackerEventRecord.occurred_at.desc()).limit(10000)
            result = await session.execute(stmt)
            records = result.scalars().all()

            if not records:
                logger.info("No telemetry records found in database.")
                return []

            logger.info(f"Retrieved {len(records)} telemetry records from database.")
            telemetry_data = []

            # Group events by (install_id, tracker_domain) to compute frequency manually
            freq_map = {}
            for r in records:
                key = (r.install_id, r.tracker_domain)
                freq_map[key] = freq_map.get(key, 0) + 1

            for r in records:
                key = (r.install_id, r.tracker_domain)
                # Infer label from classification if set, otherwise map domain rules
                db_label = (r.classification or "safe").lower()
                if db_label == "tracker":
                    db_label = "suspicious"

                telemetry_data.append({
                    "url": r.url,
                    "domain": r.tracker_domain,
                    "request_type": r.request_type or "other",
                    "referrer_domain": r.page_origin or "",
                    "third_party": 1 if r.third_party else 0,
                    "timestamp": r.occurred_at.isoformat(),
                    "request_frequency": freq_map[key],
                    "label": db_label
                })
            return telemetry_data
    except Exception as e:
        logger.warning(f"Database query failed: {e}. Fallback to synthetic telemetry builder.")
        return []


def generate_synthetic_telemetry(intermediate_data: list) -> list[dict]:
    """Generate mock telemetry data with rich behavioral features for testing/training."""
    logger.info("Generating synthetic behavioral telemetry dataset from intermediate domains...")
    telemetry_data = []

    request_types = ["script", "xmlhttprequest", "image", "sub_frame", "stylesheet", "other"]

    for idx, item in enumerate(intermediate_data):
        domain = item["domain"]
        label = item["label"]
        base_url = item["url"]

        # Determine realistic request frequency and behavioral features based on class
        if label == "safe":
            freq = random.randint(1, 4)
            third_party = 0 if random.random() < 0.8 else 1
            req_type = random.choice(["document", "image", "stylesheet", "script"])
            referrer = f"https://{domain}" if third_party == 0 else f"https://{random.choice(['google.com', 'bing.com'])}"
        elif label == "analytics":
            freq = random.randint(2, 10)
            third_party = 1
            req_type = "xmlhttprequest" if random.random() < 0.7 else "script"
            referrer = f"https://{random.choice(['example.com', 'news-site.org', 'blog.net'])}"
        elif label == "advertising":
            freq = random.randint(3, 15)
            third_party = 1
            req_type = "image" if random.random() < 0.6 else "script"
            referrer = f"https://{random.choice(['shopping-hub.com', 'games-portal.com', 'news-site.org'])}"
        elif label == "fingerprinting":
            freq = random.randint(1, 3)
            third_party = 1
            req_type = "script" if random.random() < 0.9 else "xmlhttprequest"
            referrer = f"https://{random.choice(['banking-secure.com', 'login-gate.net', 'forum.org'])}"
        else:  # suspicious
            freq = random.randint(5, 50)  # High frequency
            third_party = 1
            req_type = random.choice(["script", "xmlhttprequest", "other"])
            referrer = f"https://{random.choice(['free-downloads.cc', 'shady-redirect.top', 'adware-click.su'])}"

        # Generate timestamps over the last 24 hours
        time_offset = random.randint(0, 86400)
        timestamp = (datetime.now(timezone.utc) - timedelta(seconds=time_offset)).isoformat()

        telemetry_data.append({
            "url": base_url,
            "domain": domain,
            "request_type": req_type,
            "referrer_domain": referrer,
            "third_party": third_party,
            "timestamp": timestamp,
            "request_frequency": freq,
            "label": label
        })

    return telemetry_data


async def main():
    ensure_dirs()

    telemetry_data = []

    # In CI, skip database entirely — no engine creation, no connection pool, no hang
    if IS_CI:
        logger.info("CI environment detected. Skipping database telemetry query.")
    else:
        telemetry_data = await fetch_db_telemetry()

    # If database lacks telemetry (or CI mode), fall back to synthetic generation
    if not telemetry_data:
        intermediate_path = PROCESSED_DIR / "intermediate_domains.json"
        if not intermediate_path.exists():
            logger.error("Intermediate domains JSON not found. Run collector.py first.")
            sys.exit(1)

        with open(intermediate_path, "r", encoding="utf-8") as f:
            intermediate_data = json.load(f)

        telemetry_data = generate_synthetic_telemetry(intermediate_data)

    # Write output to telemetry directory
    output_path = TELEMETRY_DIR / "telemetry_events.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(telemetry_data, f, indent=2)

    logger.info(f"Saved {len(telemetry_data)} telemetry samples to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
