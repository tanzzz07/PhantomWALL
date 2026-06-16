import os
import sys
import pandas as pd
import numpy as np

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from training.trainer import preprocess_data, REQUEST_TYPE_MAP
from sklearn.preprocessing import LabelEncoder


def test_preprocess_data():
    # Construct a dummy DataFrame mirroring extractor features
    data = {
        "domain_length": [10, 15, 20],
        "subdomain_depth": [0, 1, 2],
        "entropy": [2.5, 3.1, 4.0],
        "tld": ["com", "org", "xyz"],
        "tld_risk_score": [0.1, 0.1, 1.0],
        "digit_ratio": [0.0, 0.1, 0.2],
        "hyphen_count": [0, 1, 0],
        "url_length": [50, 60, 80],
        "path_depth": [1, 2, 3],
        "query_parameter_count": [0, 1, 3],
        "query_parameter_length": [0, 10, 25],
        "special_character_count": [2, 5, 8],
        "analytics_keyword_score": [0, 0, 1],
        "advertising_keyword_score": [1, 0, 0],
        "fingerprinting_keyword_score": [0, 1, 0],
        "tracker_keyword_score": [0, 0, 1],
        "third_party_flag": [0, 1, 1],
        "request_frequency": [1, 5, 20],
        "request_type": ["image", "script", "other"],
        "referrer_domain_similarity": [1.0, 0.0, 0.2],
        "session_occurrence_count": [1, 5, 20],
        "suspicious_character_count": [0, 1, 3],
        "encoded_character_ratio": [0.0, 0.0, 0.05],
        "high_entropy_subdomain": [0, 0, 1],
        "tracking_pattern_score": [0.0, 0.5, 1.0],
        "label": ["safe", "fingerprinting", "suspicious"]
    }
    
    df = pd.DataFrame(data)
    
    X, y, feature_names, label_encoder = preprocess_data(df)
    
    # Check shape
    assert X.shape[0] == 3
    assert X.shape[1] == 24  # 25 original columns minus 'label' and 'tld'
    assert len(y) == 3
    
    # Check mapping logic
    assert X.loc[0, "request_type"] == REQUEST_TYPE_MAP["image"]
    assert X.loc[1, "request_type"] == REQUEST_TYPE_MAP["script"]
    assert X.loc[2, "request_type"] == REQUEST_TYPE_MAP["other"]
    
    # Label verification
    assert isinstance(label_encoder, LabelEncoder)
    assert set(label_encoder.classes_) == {"safe", "fingerprinting", "suspicious"}
