import os
import re
import json
import logging
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# URL constants
EASYLIST_URL = "https://easylist.to/easylist/easylist.txt"
EASYPRIVACY_URL = "https://easylist.to/easylist/easyprivacy.txt"
DISCONNECT_URL = "https://raw.githubusercontent.com/disconnectme/disconnect-tracking-protection/master/services.json"
TRANCO_URL = "https://tranco-list.eu/download/daily/tranco_10000.csv"


def ensure_dirs():
    """Ensure directory structure exists."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, filename: str) -> Path:
    """Download a file and save it to raw data directory."""
    dest = RAW_DIR / filename
    logger.info(f"Downloading {url} to {dest}...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(dest, "w", encoding="utf-8") as f:
            f.write(response.text)
        logger.info(f"Successfully downloaded {filename}")
        return dest
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}. Local fallback will be used if needed.")
        return dest


def parse_adblock_list(file_path: Path) -> set:
    """Parse domains/rules from EasyList/EasyPrivacy Adblock-style syntax."""
    domains = set()
    if not file_path.exists():
        return domains

    # Match rules like ||example.com^
    rule_regex = re.compile(r"^\|\|([a-z0-9]+(?:[-.][a-z0-9]+)*\.[a-z]{2,})(?:\^|/|\$)")
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().lower()
            if not line or line.startswith("!"):
                continue
            match = rule_regex.match(line)
            if match:
                domains.add(match.group(1))
    return domains


def parse_disconnect_list(file_path: Path) -> dict:
    """Parse Disconnect services JSON list into classified domains."""
    classified = {
        "analytics": set(),
        "advertising": set(),
        "fingerprinting": set(),
        "suspicious": set()
    }
    if not file_path.exists():
        return classified

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        categories = data.get("categories", {})
        for cat_name, services in categories.items():
            # Map Disconnect categories to PhantomWALL target classes
            target_class = "suspicious"
            cat_lower = cat_name.lower()
            if "analytics" in cat_lower:
                target_class = "analytics"
            elif "advertising" in cat_lower:
                target_class = "advertising"
            elif "fingerprinting" in cat_lower:
                target_class = "fingerprinting"
            
            for service in services:
                for entity in service.values():
                    if isinstance(entity, dict):
                        for domain_list in entity.values():
                            if isinstance(domain_list, list):
                                for d in domain_list:
                                    d_clean = d.strip().lower()
                                    if d_clean:
                                        classified[target_class].add(d_clean)
    except Exception as e:
        logger.error(f"Error parsing Disconnect JSON: {e}")
    return classified


def parse_tranco_list(file_path: Path) -> set:
    """Parse Tranco top domains list."""
    domains = set()
    if not file_path.exists():
        return domains

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                domain = parts[1].strip().lower()
                if domain:
                    domains.add(domain)
    return domains


def generate_mock_data():
    """Generate high-quality synthetic/mock tracking and safe domain datasets for offline execution."""
    logger.info("Generating robust mock datasets for offline execution...")
    
    mock_safe = [
        "google.com", "youtube.com", "facebook.com", "wikipedia.org", "yahoo.com", "amazon.com",
        "twitter.com", "instagram.com", "linkedin.com", "reddit.com", "netflix.com", "github.com",
        "microsoft.com", "apple.com", "cloudflare.com", "zoom.us", "twitch.tv", "medium.com",
        "stackoverflow.com", "openai.com", "spotify.com", "pinterest.com", "bbc.co.uk", "cnn.com"
    ]
    
    mock_analytics = [
        "google-analytics.com", "ga.js", "analytics.local", "mixpanel.com", "segment.io", "amplitude.com",
        "hotjar.com", "heap.io", "optimizely.com", "pendo.io", "matomo.org", "statcounter.com",
        "newrelic.com", "datadoghq.com", "sentry.io", "loggly.com", "crazyegg.com", "kissmetrics.com"
    ]
    
    mock_advertising = [
        "doubleclick.net", "adservice.google.com", "adnxs.com", "rubiconproject.com", "pubmatic.com",
        "criteo.com", "taboola.com", "outbrain.com", "adroll.com", "smartadserver.com", "bidswitch.net",
        "popads.net", "exoclick.com", "media.net", "indexww.com", "openx.net", "sovrn.com"
    ]
    
    mock_fingerprinting = [
        "fingerprint.com", "fingerprintjs.com", "fp.js", "canvas-fingerprinting.xyz", "fontdetector.org",
        "mime-type-logger.net", "browser-leaks-collector.ru", "device-fingerprint.cn", "audio-fingerprint.com",
        "webrtc-ip-leak.net", "canvas-blocker-bypass.io", "clientjs.org"
    ]
    
    mock_suspicious = [
        "coinhive.com", "miner.xyz", "malicious-tracker.cc", "adware-server.ru", "redirect-loop.top",
        "spam-url.xyz", "phishing-landing.xyz", "ransomware-beacon.cn", "compromised-cdn.su",
        "malvertising-network.gq", "tracking-pixel.cc", "suspicious-beacon.io"
    ]

    # Write them in processed format
    processed_data = []
    
    for domain in mock_safe:
        processed_data.append({"url": f"https://{domain}/index.html", "domain": domain, "label": "safe", "request_type": "document", "third_party": 0})
        processed_data.append({"url": f"https://{domain}/static/logo.png", "domain": domain, "label": "safe", "request_type": "image", "third_party": 0})
        processed_data.append({"url": f"https://{domain}/static/styles.css", "domain": domain, "label": "safe", "request_type": "stylesheet", "third_party": 0})
        
    for domain in mock_analytics:
        processed_data.append({"url": f"https://{domain}/collect?v=1&tid=123", "domain": domain, "label": "analytics", "request_type": "xmlhttprequest", "third_party": 1})
        processed_data.append({"url": f"https://{domain}/analytics.js", "domain": domain, "label": "analytics", "request_type": "script", "third_party": 1})
        
    for domain in mock_advertising:
        processed_data.append({"url": f"https://{domain}/ad?size=300x250", "domain": domain, "label": "advertising", "request_type": "image", "third_party": 1})
        processed_data.append({"url": f"https://{domain}/bid?imp=45", "domain": domain, "label": "advertising", "request_type": "xmlhttprequest", "third_party": 1})
        
    for domain in mock_fingerprinting:
        processed_data.append({"url": f"https://{domain}/fp.js", "domain": domain, "label": "fingerprinting", "request_type": "script", "third_party": 1})
        processed_data.append({"url": f"https://{domain}/collect?canvas=1", "domain": domain, "label": "fingerprinting", "request_type": "xmlhttprequest", "third_party": 1})
        
    for domain in mock_suspicious:
        processed_data.append({"url": f"https://{domain}/miner.js", "domain": domain, "label": "suspicious", "request_type": "script", "third_party": 1})
        processed_data.append({"url": f"https://{domain}/ping?token=xyz", "domain": domain, "label": "suspicious", "request_type": "other", "third_party": 1})

    # Save to intermediate JSON
    with open(PROCESSED_DIR / "intermediate_domains.json", "w", encoding="utf-8") as f:
        json.dump(processed_data, f, indent=2)
    logger.info(f"Saved {len(processed_data)} mock samples to {PROCESSED_DIR / 'intermediate_domains.json'}")


def run():
    """Execute dataset collection."""
    ensure_dirs()
    
    # Download lists
    download_file(EASYLIST_URL, "easylist.txt")
    download_file(EASYPRIVACY_URL, "easyprivacy.txt")
    download_file(DISCONNECT_URL, "disconnect_services.json")
    download_file(TRANCO_URL, "tranco_top_domains.csv")
    
    # Check if files downloaded successfully and have content
    easylist_path = RAW_DIR / "easylist.txt"
    easyprivacy_path = RAW_DIR / "easyprivacy.txt"
    disconnect_path = RAW_DIR / "disconnect_services.json"
    tranco_path = RAW_DIR / "tranco_top_domains.csv"
    
    has_internet = (
        easylist_path.exists() and easylist_path.stat().st_size > 1000 and
        easyprivacy_path.exists() and easyprivacy_path.stat().st_size > 1000 and
        disconnect_path.exists() and disconnect_path.stat().st_size > 1000
    )
    
    if not has_internet:
        logger.warning("Network resources unavailable or incomplete. Generating fallback mock data.")
        generate_mock_data()
        return

    logger.info("Processing downloaded lists...")
    easylist_domains = parse_adblock_list(easylist_path)
    easyprivacy_domains = parse_adblock_list(easyprivacy_path)
    disconnect_data = parse_disconnect_list(disconnect_path)
    tranco_domains = list(parse_tranco_list(tranco_path))[:5000]  # Use top 5000 safe domains
    if not tranco_domains:
        logger.warning("Tranco domains empty (possibly download failed). Using default mock safe domains.")
        tranco_domains = [
            "google.com", "youtube.com", "facebook.com", "wikipedia.org", "yahoo.com", "amazon.com",
            "twitter.com", "instagram.com", "linkedin.com", "reddit.com", "netflix.com", "github.com",
            "microsoft.com", "apple.com", "cloudflare.com", "zoom.us", "twitch.tv", "medium.com",
            "stackoverflow.com", "openai.com", "spotify.com", "pinterest.com", "bbc.co.uk", "cnn.com"
        ]

    logger.info(f"Loaded: EasyList ({len(easylist_domains)}), EasyPrivacy ({len(easyprivacy_domains)}), Disconnect Categories, Tranco ({len(tranco_domains)})")

    # Combine into intermediate dataset
    processed_data = []

    # 1. Safe domains from Tranco
    for domain in tranco_domains:
        # Ignore if listed as tracker elsewhere
        if (domain in easylist_domains or 
                domain in easyprivacy_domains or 
                any(domain in ds for ds in disconnect_data.values())):
            continue
        processed_data.append({
            "url": f"https://{domain}/",
            "domain": domain,
            "label": "safe",
            "request_type": "document",
            "third_party": 0
        })

    # Helper to clean/check lists
    def add_from_list(domains_list, label, req_type, tp):
        for domain in domains_list:
            if domain in tranco_domains[:100]:  # Ensure no overlap with super popular safe domains
                continue
            processed_data.append({
                "url": f"https://{domain}/tracker.js" if req_type == "script" else f"https://{domain}/pixel",
                "domain": domain,
                "label": label,
                "request_type": req_type,
                "third_party": tp
            })

    # 2. Analytics from EasyPrivacy & Disconnect
    analytics_domains = easyprivacy_domains.union(disconnect_data["analytics"])
    add_from_list(list(analytics_domains)[:3000], "analytics", "script", 1)

    # 3. Advertising from EasyList & Disconnect
    ad_domains = easylist_domains.union(disconnect_data["advertising"])
    add_from_list(list(ad_domains)[:3000], "advertising", "image", 1)

    # 4. Fingerprinting
    add_from_list(list(disconnect_data["fingerprinting"])[:1500], "fingerprinting", "script", 1)

    # 5. Suspicious
    add_from_list(list(disconnect_data["suspicious"])[:1500], "suspicious", "other", 1)

    # Save to intermediate JSON
    with open(PROCESSED_DIR / "intermediate_domains.json", "w", encoding="utf-8") as f:
        json.dump(processed_data, f, indent=2)
    logger.info(f"Successfully saved {len(processed_data)} items to intermediate_domains.json")


if __name__ == "__main__":
    run()
