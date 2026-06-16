import re
import math
import logging
import json
from collections import Counter
from urllib.parse import urlparse, parse_qsl
from pathlib import Path
import pandas as pd
import tldextract

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# High risk TLDs definition
HIGH_RISK_TLDS = {
    "xyz", "top", "tk", "cf", "gq", "ml", "ga", "club", "download", "work", 
    "click", "bid", "loan", "men", "win", "ru", "cn", "su", "gdn", "date"
}

# Keywords definitions
ANALYTICS_KEYWORDS = ["analytics", "telemetry", "stats", "metric", "event", "measure", "ga.js"]
ADVERTISING_KEYWORDS = ["ad", "ads", "doubleclick", "banner", "pop", "pixel", "sponsor", "click", "campaign", "marketing", "syndication"]
FINGERPRINTING_KEYWORDS = ["fingerprint", "fp.js", "canvas", "webgl", "font", "clientjs", "navigator", "user-agent", "mime", "screen"]
TRACKER_KEYWORDS = ["track", "tracker", "tracking", "collect", "log"]


class FeatureExtractor:
    """Extracts features from browser network request telemetry for ML models."""

    @staticmethod
    def calculate_entropy(text: str) -> float:
        """Calculate Shannon Entropy of a string."""
        if not text:
            return 0.0
        counts = Counter(text)
        total = len(text)
        return -sum((count / total) * math.log2(count / total) for count in counts.values())

    @staticmethod
    def get_referrer_similarity(domain: str, referrer: str) -> float:
        """Calculate string similarity/relationship between request domain and referrer."""
        if not referrer:
            return 0.0
        try:
            ref_parsed = urlparse(referrer.lower())
            ref_domain = ref_parsed.netloc
            if not ref_domain:
                ref_domain = referrer.lower()
            
            domain = domain.lower()
            if domain == ref_domain:
                return 1.0
            
            # Subdomain check
            if domain.endswith("." + ref_domain) or ref_domain.endswith("." + domain):
                return 0.8
                
            # Overlap coefficient
            d_set = set(domain)
            r_set = set(ref_domain)
            intersection = len(d_set.intersection(r_set))
            min_len = min(len(d_set), len(r_set))
            if min_len > 0:
                return intersection / min_len
        except Exception:
            pass
        return 0.0

    @classmethod
    def extract_features(
        cls,
        url: str,
        request_type: str,
        third_party: bool | int,
        request_frequency: int = 1,
        referrer_domain: str = "",
        session_occurrence_count: int = 1
    ) -> dict:
        """Extract all 20+ features required by PhantomWALL classifier."""
        url_lower = url.lower()
        
        # 1. Parse URL & Extract domain/subdomain using tldextract
        try:
            parsed = urlparse(url_lower)
            raw_host = parsed.netloc or parsed.path.split("/")[0]
            # Strip port if present
            if ":" in raw_host:
                raw_host = raw_host.split(":")[0]
        except Exception:
            raw_host = url_lower
            
        try:
            ext = tldextract.extract(raw_host)
            domain = ext.registered_domain or raw_host
            subdomain = ext.subdomain
            tld = ext.suffix
        except Exception:
            domain = raw_host
            subdomain = ""
            tld = ""

        domain_lower = domain.lower()

        # Domain Features
        domain_length = len(domain_lower)
        subdomain_depth = len(subdomain.split(".")) if subdomain else 0
        entropy = cls.calculate_entropy(domain_lower)
        tld_risk_score = 1.0 if tld.lower() in HIGH_RISK_TLDS else 0.1
        
        digits = sum(c.isdigit() for c in domain_lower)
        digit_ratio = digits / domain_length if domain_length > 0 else 0.0
        hyphen_count = domain_lower.count("-")

        # URL Features
        url_length = len(url_lower)
        path = parsed.path if 'parsed' in locals() else ""
        path_depth = path.count("/")
        
        query = parsed.query if 'parsed' in locals() else ""
        try:
            params = parse_qsl(query)
            query_parameter_count = len(params)
        except Exception:
            query_parameter_count = 0
            
        query_parameter_length = len(query)
        
        special_chars = "?&=%+-_. ,;@$!"
        special_character_count = sum(url_lower.count(c) for c in special_chars)

        # Keyword Features
        # Match keywords in path, query, and domain
        def calculate_keyword_score(keywords: list) -> int:
            score = 0
            for kw in keywords:
                if kw in url_lower:
                    score += 1
            return score

        analytics_keyword_score = calculate_keyword_score(ANALYTICS_KEYWORDS)
        advertising_keyword_score = calculate_keyword_score(ADVERTISING_KEYWORDS)
        fingerprinting_keyword_score = calculate_keyword_score(FINGERPRINTING_KEYWORDS)
        tracker_keyword_score = calculate_keyword_score(TRACKER_KEYWORDS)

        # Behavioral Features
        third_party_flag = 1 if third_party else 0
        referrer_domain_similarity = cls.get_referrer_similarity(domain_lower, referrer_domain)

        # Security Features
        suspicious_chars = ";(){}[]<>\\'\"`"
        suspicious_character_count = sum(url_lower.count(c) for c in suspicious_chars)
        
        pct_count = url_lower.count("%")
        encoded_character_ratio = pct_count / url_length if url_length > 0 else 0.0
        
        subdomain_entropy = cls.calculate_entropy(subdomain) if subdomain else 0.0
        high_entropy_subdomain = 1 if subdomain_entropy > 3.5 else 0

        # Pattern scoring (high importance tracking signatures)
        tracking_pattern_score = 0.0
        # Check tracking parameters common to analytics/ads
        tracking_params = ["utm_", "gclid", "fbclid", "clickid", "affiliate", "pixel", "callback"]
        if any(p in query for p in tracking_params):
            tracking_pattern_score += 0.5
        if any(p in path for p in ["/pixel", "/collect", "/track", "/adserver"]):
            tracking_pattern_score += 0.5

        return {
            "domain_length": domain_length,
            "subdomain_depth": subdomain_depth,
            "entropy": entropy,
            "tld": tld,
            "tld_risk_score": tld_risk_score,
            "digit_ratio": digit_ratio,
            "hyphen_count": hyphen_count,
            "url_length": url_length,
            "path_depth": path_depth,
            "query_parameter_count": query_parameter_count,
            "query_parameter_length": query_parameter_length,
            "special_character_count": special_character_count,
            "analytics_keyword_score": analytics_keyword_score,
            "advertising_keyword_score": advertising_keyword_score,
            "fingerprinting_keyword_score": fingerprinting_keyword_score,
            "tracker_keyword_score": tracker_keyword_score,
            "third_party_flag": third_party_flag,
            "request_frequency": request_frequency,
            "request_type": request_type,
            "referrer_domain_similarity": referrer_domain_similarity,
            "session_occurrence_count": session_occurrence_count,
            "suspicious_character_count": suspicious_character_count,
            "encoded_character_ratio": encoded_character_ratio,
            "high_entropy_subdomain": high_entropy_subdomain,
            "tracking_pattern_score": tracking_pattern_score
        }


def generate_final_dataset():
    """Load telemetry samples, extract features, and build final CSV dataset."""
    logger.info("Starting dataset generation & feature extraction pipeline...")
    
    telemetry_path = Path(__file__).resolve().parent.parent / "data" / "telemetry" / "telemetry_events.json"
    final_dir = Path(__file__).resolve().parent.parent / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    
    if not telemetry_path.exists():
        logger.error(f"Telemetry events file not found at {telemetry_path}. Run collector and builder first.")
        return

    with open(telemetry_path, "r", encoding="utf-8") as f:
        events = json.load(f)
        
    logger.info(f"Loaded {len(events)} telemetry events. Beginning feature extraction...")
    
    records = []
    for idx, e in enumerate(events):
        try:
            features = FeatureExtractor.extract_features(
                url=e["url"],
                request_type=e["request_type"],
                third_party=e["third_party"],
                request_frequency=e["request_frequency"],
                referrer_domain=e.get("referrer_domain", ""),
                session_occurrence_count=e.get("request_frequency", 1)  # Using frequency as proxy for occurrence
            )
            features["label"] = e["label"]
            records.append(features)
        except Exception as ex:
            logger.error(f"Failed to extract features for event {idx}: {ex}")

    df = pd.DataFrame(records)
    
    output_path = final_dir / "phantomwall_dataset.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Successfully generated final dataset at {output_path} with shape {df.shape}")


if __name__ == "__main__":
    generate_final_dataset()
