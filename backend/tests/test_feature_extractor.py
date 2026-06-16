import os
import sys

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from feature_engineering.extractor import FeatureExtractor


def test_feature_extraction_structure():
    url = "https://www.google-analytics.com/g/collect?v=2&tid=UA-1234&cid=555"
    req_type = "xmlhttprequest"
    third_party = True
    
    features = FeatureExtractor.extract_features(
        url=url,
        request_type=req_type,
        third_party=third_party,
        request_frequency=2,
        referrer_domain="https://example.com"
    )
    
    assert isinstance(features, dict)
    
    # Assert existence of key features
    expected_keys = [
        "domain_length", "subdomain_depth", "entropy", "tld", "tld_risk_score",
        "digit_ratio", "hyphen_count", "url_length", "path_depth",
        "query_parameter_count", "query_parameter_length", "special_character_count",
        "analytics_keyword_score", "advertising_keyword_score",
        "fingerprinting_keyword_score", "tracker_keyword_score",
        "third_party_flag", "request_frequency", "request_type",
        "referrer_domain_similarity", "session_occurrence_count",
        "suspicious_character_count", "encoded_character_ratio",
        "high_entropy_subdomain", "tracking_pattern_score"
    ]
    for key in expected_keys:
        assert key in features, f"Missing key {key} in extracted features."


def test_feature_values_logic():
    url = "http://localhost/ad/banner-ad.png?size=300x250"
    features = FeatureExtractor.extract_features(
        url=url,
        request_type="image",
        third_party=False,
        request_frequency=5
    )
    
    assert features["third_party_flag"] == 0
    assert features["request_frequency"] == 5
    assert features["request_type"] == "image"
    assert features["advertising_keyword_score"] > 0
    assert features["query_parameter_count"] == 1
    assert features["tld_risk_score"] == 0.1  # localhost has standard low risk suffix fallback


def test_entropy():
    # High entropy domain vs low entropy domain
    low_ent = FeatureExtractor.calculate_entropy("aaaa")
    high_ent = FeatureExtractor.calculate_entropy("abcd")
    assert low_ent == 0.0
    assert high_ent > 1.5
