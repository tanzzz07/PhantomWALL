import os
import sys
import re
import json
import random
import logging
import pandas as pd
import numpy as np
from pathlib import Path
import tldextract

# Resolve path for backend imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dataset_pipeline.collector import parse_adblock_list, parse_disconnect_list, parse_tranco_list
from feature_engineering.extractor import FeatureExtractor

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FINAL_DIR = DATA_DIR / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

# Dataset paths
BALANCED_URLS_PATH = DATA_DIR / "balanced_urls.csv" / "balanced_urls.csv"
PHISHING_URLS_PATH = DATA_DIR / "phishing_url_dataset_unique.csv"

# Static list paths
EASYLIST_PATH = RAW_DIR / "easylist.txt"
EASYPRIVACY_PATH = RAW_DIR / "easyprivacy.txt"
DISCONNECT_PATH = RAW_DIR / "disconnect_services.json"
TRANCO_PATH = RAW_DIR / "tranco_top_domains.csv"


def clean_url_series(s: pd.Series) -> pd.Series:
    """Standardize URLs in a pandas Series."""
    s = s.fillna("").astype(str).str.strip()
    starts_with_http = s.str.startswith("http://") | s.str.startswith("https://")
    return np.where(starts_with_http, s, "http://" + s)


def main():
    logger.info("Starting build_kaggle_dataset pipeline...")

    # 1. Load static lists for taxonomy mapping and deduplication
    logger.info("Loading static lists...")
    easylist_domains = parse_adblock_list(EASYLIST_PATH)
    easyprivacy_domains = parse_adblock_list(EASYPRIVACY_PATH)
    disconnect_data = parse_disconnect_list(DISCONNECT_PATH)
    tranco_domains = parse_tranco_list(TRANCO_PATH)

    if not tranco_domains:
        logger.warning("Tranco top domains list empty. Using fallback popular domains list.")
        tranco_domains = {
            "google.com", "youtube.com", "facebook.com", "wikipedia.org", "yahoo.com", "amazon.com",
            "twitter.com", "instagram.com", "linkedin.com", "reddit.com", "netflix.com", "github.com",
            "microsoft.com", "apple.com", "cloudflare.com", "zoom.us", "twitch.tv", "medium.com",
            "stackoverflow.com", "openai.com", "spotify.com", "pinterest.com", "bbc.co.uk", "cnn.com"
        }

    logger.info(f"Loaded static lists: EasyList ({len(easylist_domains)}), EasyPrivacy ({len(easyprivacy_domains)}), "
                f"Disconnect categories, Tranco ({len(tranco_domains)})")

    # 2. Load and merge Kaggle datasets
    logger.info("Loading Kaggle datasets...")
    
    if not BALANCED_URLS_PATH.exists():
        logger.error(f"Balanced URLs dataset not found at {BALANCED_URLS_PATH}")
        sys.exit(1)
    if not PHISHING_URLS_PATH.exists():
        logger.error(f"Phishing dataset not found at {PHISHING_URLS_PATH}")
        sys.exit(1)

    balanced_df = pd.read_csv(BALANCED_URLS_PATH, usecols=["url", "label"])
    phishing_df = pd.read_csv(PHISHING_URLS_PATH, usecols=["url", "label"])

    logger.info(f"Loaded balanced_urls.csv: {len(balanced_df)} rows")
    logger.info(f"Loaded phishing_url_dataset_unique.csv: {len(phishing_df)} rows")

    # Standardize and merge using vectorized ops
    balanced_df["url"] = clean_url_series(balanced_df["url"])
    balanced_df["initial_label"] = np.where(balanced_df["label"].astype(str).str.strip().str.lower() == "malicious", "suspicious", "benign")
    balanced_df = balanced_df[["url", "initial_label"]]

    phishing_df["url"] = clean_url_series(phishing_df["url"])
    phishing_df["initial_label"] = np.where(phishing_df["label"].astype(str).str.strip().isin(["1", "1.0"]), "suspicious", "benign")
    phishing_df = phishing_df[["url", "initial_label"]]

    merged_df = pd.concat([balanced_df, phishing_df], ignore_index=True)
    logger.info(f"Total merged raw URLs: {len(merged_df)}")
    
    merged_df = merged_df[merged_df["url"] != ""]
    merged_df = merged_df.drop_duplicates(subset=["url"])
    logger.info(f"Unique merged URLs: {len(merged_df)}")

    # 3. Extract domain and apply Taxonomy Mapping & Deduplication rules
    logger.info("Extracting domains using tldextract...")
    
    extract_parser = tldextract.TLDExtract()
    urls = merged_df["url"].tolist()
    
    domain_cache = {}
    domains = []
    for u in urls:
        try:
            host = u.split("://")[-1].split("/")[0].split(":")[0].lower()
            if host not in domain_cache:
                domain_cache[host] = extract_parser(host).registered_domain or host
            domains.append(domain_cache[host])
        except Exception:
            domains.append("")

    merged_df["domain"] = domains
    merged_df = merged_df[merged_df["domain"] != ""]
    
    logger.info("Applying taxonomy mapping and deduplication...")
    easyprivacy_set = set(easyprivacy_domains)
    easylist_set = set(easylist_domains)
    disc_fingerprinting = set(disconnect_data.get("fingerprinting", set()))
    disc_analytics = set(disconnect_data.get("analytics", set()))
    disc_advertising = set(disconnect_data.get("advertising", set()))
    disc_suspicious = set(disconnect_data.get("suspicious", set()))
    tranco_set = set(tranco_domains)

    # Keyword mappings
    ANALYTICS_KEYWORDS = ["analytics", "telemetry", "stats", "metric", "event", "measure", "ga.js"]
    ADVERTISING_KEYWORDS = ["ad", "ads", "doubleclick", "banner", "pop", "pixel", "sponsor", "click", "campaign", "marketing", "syndication"]
    FINGERPRINTING_KEYWORDS = ["fingerprint", "fp.js", "canvas", "webgl", "font", "clientjs", "navigator", "user-agent", "mime", "screen"]

    def has_keyword_series(s, keywords):
        s_lower = s.str.lower()
        mask = pd.Series(False, index=s.index)
        for kw in keywords:
            mask |= s_lower.str.contains(re.escape(kw), regex=True)
        return mask

    # Check matches
    urls_series = merged_df["url"]
    is_fp = merged_df["domain"].isin(disc_fingerprinting) | has_keyword_series(urls_series, FINGERPRINTING_KEYWORDS)
    is_analytics = merged_df["domain"].isin(easyprivacy_set) | merged_df["domain"].isin(disc_analytics) | has_keyword_series(urls_series, ANALYTICS_KEYWORDS)
    is_advertising = merged_df["domain"].isin(easylist_set) | merged_df["domain"].isin(disc_advertising) | has_keyword_series(urls_series, ADVERTISING_KEYWORDS)
    is_suspicious_tracker = merged_df["domain"].isin(disc_suspicious)

    # Assign taxonomy labels
    merged_df["mapped_class"] = None
    merged_df.loc[is_fp, "mapped_class"] = "fingerprinting"
    merged_df.loc[merged_df["mapped_class"].isna() & is_analytics, "mapped_class"] = "analytics"
    merged_df.loc[merged_df["mapped_class"].isna() & is_advertising, "mapped_class"] = "advertising"
    merged_df.loc[merged_df["mapped_class"].isna() & is_suspicious_tracker, "mapped_class"] = "suspicious"

    # Deduplication and Filtering
    # Remove tracker classes that overlap with Tranco whitelist
    is_in_tranco = merged_df["domain"].isin(tranco_set)
    merged_df = merged_df[~(merged_df["mapped_class"].notna() & is_in_tranco)]

    # Separate mapped trackers and raw labels
    mapped_df = merged_df[merged_df["mapped_class"].notna()].copy()
    mapped_df["final_label"] = mapped_df["mapped_class"]

    unmapped_df = merged_df[merged_df["mapped_class"].isna()].copy()

    # Suspicious (from malicious/1): exclude Tranco whitelist
    susp_unmapped = unmapped_df[unmapped_df["initial_label"] == "suspicious"].copy()
    susp_unmapped = susp_unmapped[~susp_unmapped["domain"].isin(tranco_set)]
    susp_unmapped["final_label"] = "suspicious"

    # Benign (from benign/0): safe category
    benign_unmapped = unmapped_df[unmapped_df["initial_label"] == "benign"].copy()
    benign_unmapped["final_label"] = "safe"

    # Combine back
    final_classified_df = pd.concat([mapped_df, susp_unmapped, benign_unmapped], ignore_index=True)
    
    # Remove duplicate domains to avoid split leakage and redundancy
    final_classified_df = final_classified_df.drop_duplicates(subset=["domain"])

    # Backfill blocklist domains for underrepresented classes
    counts = final_classified_df["final_label"].value_counts()
    logger.info(f"Class sizes before backfilling: \n{counts}")

    # Pre-compute existing domains set for O(1) membership lookup
    existing_domains = set(final_classified_df["domain"])

    # Backfill fingerprinting to reach at least 1500 samples
    fp_count = counts.get("fingerprinting", 0)
    if fp_count < 1500:
        logger.info(f"Backfilling fingerprinting from Disconnect list...")
        added = 0
        added_records = []
        for domain in disc_fingerprinting:
            if domain not in existing_domains and domain not in tranco_set:
                added_records.append({
                    "url": f"https://{domain}/fp.js",
                    "domain": domain,
                    "initial_label": "suspicious",
                    "mapped_class": "fingerprinting",
                    "final_label": "fingerprinting"
                })
                existing_domains.add(domain)
                added += 1
        if added_records:
            final_classified_df = pd.concat([final_classified_df, pd.DataFrame(added_records)], ignore_index=True)
        logger.info(f"Added {added} fingerprinting domains from Disconnect list.")

    # Backfill analytics to reach at least 1500 samples
    analytics_count = final_classified_df["final_label"].value_counts().get("analytics", 0)
    if analytics_count < 1500:
        logger.info(f"Backfilling analytics from EasyPrivacy and Disconnect...")
        added = 0
        added_records = []
        all_analytics_domains = list(easyprivacy_set.union(disc_analytics))
        for domain in all_analytics_domains:
            if domain not in existing_domains and domain not in tranco_set:
                added_records.append({
                    "url": f"https://{domain}/tracker.js",
                    "domain": domain,
                    "initial_label": "suspicious",
                    "mapped_class": "analytics",
                    "final_label": "analytics"
                })
                existing_domains.add(domain)
                added += 1
                if added + analytics_count >= 1500:
                    break
        if added_records:
            final_classified_df = pd.concat([final_classified_df, pd.DataFrame(added_records)], ignore_index=True)
        logger.info(f"Added {added} analytics domains from static lists.")

    # Backfill advertising to reach at least 1500 samples
    advertising_count = final_classified_df["final_label"].value_counts().get("advertising", 0)
    if advertising_count < 1500:
        logger.info(f"Backfilling advertising from EasyList and Disconnect...")
        added = 0
        added_records = []
        all_advertising_domains = list(easylist_set.union(disc_advertising))
        for domain in all_advertising_domains:
            if domain not in existing_domains and domain not in tranco_set:
                added_records.append({
                    "url": f"https://{domain}/pixel",
                    "domain": domain,
                    "initial_label": "suspicious",
                    "mapped_class": "advertising",
                    "final_label": "advertising"
                })
                existing_domains.add(domain)
                added += 1
                if added + advertising_count >= 1500:
                    break
        if added_records:
            final_classified_df = pd.concat([final_classified_df, pd.DataFrame(added_records)], ignore_index=True)
        logger.info(f"Added {added} advertising domains from static lists.")

    # Recalculate class sizes
    grouped = final_classified_df.groupby("final_label")
    class_sizes = grouped.size()
    logger.info(f"Class sizes after backfilling:\n{class_sizes}")

    min_size = class_sizes.min()
    logger.info(f"Smallest class size is {min_size}.")

    if min_size == 0:
        logger.error("One of the classes has 0 samples. Cannot balance dataset.")
        sys.exit(1)

    # Sample equally
    balanced_dfs = []
    for label, group in grouped:
        balanced_dfs.append(group.sample(n=min_size, random_state=42))

    balanced_df = pd.concat(balanced_dfs, ignore_index=True)
    logger.info(f"Total balanced samples: {len(balanced_df)}")

    # 5. Generate request/behavioral attributes & extract features
    logger.info("Extracting features using FeatureExtractor...")
    
    records = balanced_df.to_dict("records")
    final_records = []
    
    for idx, r in enumerate(records):
        url = r["url"]
        domain = r["domain"]
        label = r["final_label"]

        # Infer request type dynamically from URL or default realistically
        url_lower = url.lower()
        if ".js" in url_lower or "fp.js" in url_lower:
            req_type = "script"
        elif any(ext in url_lower for ext in [".png", ".gif", ".jpg", ".jpeg", "/pixel"]):
            req_type = "image"
        elif any(term in url_lower for term in ["/collect", "/analytics", "/telemetry"]):
            req_type = "xmlhttprequest"
        else:
            if label == "safe":
                req_type = random.choice(["document", "image", "stylesheet", "script"])
            elif label == "analytics":
                req_type = random.choice(["xmlhttprequest", "script", "other"])
            elif label == "advertising":
                req_type = random.choice(["image", "script", "other", "xmlhttprequest"])
            elif label == "fingerprinting":
                req_type = random.choice(["script", "xmlhttprequest", "other"])
            else:  # suspicious
                req_type = random.choice(["script", "xmlhttprequest", "other"])

        # Ensure overlapping frequency ranges so the classifier relies on robust URL keywords and structures
        if label == "safe":
            freq = random.randint(1, 10)
            third_party = 0 if random.random() < 0.8 else 1
            referrer = f"https://{domain}" if third_party == 0 else f"https://{random.choice(['google.com', 'bing.com'])}"
        elif label == "analytics":
            freq = random.randint(1, 30)
            third_party = 1
            referrer = f"https://{random.choice(['example.com', 'news-site.org', 'blog.net'])}"
        elif label == "advertising":
            freq = random.randint(1, 30)
            third_party = 1
            referrer = f"https://{random.choice(['shopping-hub.com', 'games-portal.com', 'news-site.org'])}"
        elif label == "fingerprinting":
            freq = random.randint(1, 30)
            third_party = 1
            referrer = f"https://{random.choice(['banking-secure.com', 'login-gate.net', 'forum.org'])}"
        else:  # suspicious
            freq = random.randint(1, 50)
            third_party = 1
            referrer = f"https://{random.choice(['free-downloads.cc', 'shady-redirect.top', 'adware-click.su'])}"

        try:
            features = FeatureExtractor.extract_features(
                url=url,
                request_type=req_type,
                third_party=third_party,
                request_frequency=freq,
                referrer_domain=referrer,
                session_occurrence_count=freq
            )
            features["label"] = label
            final_records.append(features)
        except Exception as ex:
            logger.error(f"Failed feature extraction for URL {url}: {ex}")

    # 6. Save final CSV
    final_df = pd.DataFrame(final_records)
    output_path = FINAL_DIR / "phantomwall_dataset.csv"
    final_df.to_csv(output_path, index=False)
    
    logger.info(f"Successfully exported final balanced dataset to {output_path} with shape {final_df.shape}")


if __name__ == "__main__":
    main()
