import os
import sys
import json
from pathlib import Path

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dataset_pipeline.collector import generate_mock_data, PROCESSED_DIR
from dataset_pipeline.telemetry_dataset_builder import generate_synthetic_telemetry


def test_collector_mock_generation(tmp_path):
    # Call generate_mock_data and verify it writes intermediate_domains.json
    generate_mock_data()
    
    intermediate_path = PROCESSED_DIR / "intermediate_domains.json"
    assert intermediate_path.exists()
    
    with open(intermediate_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert isinstance(data, list)
    assert len(data) > 0
    assert "url" in data[0]
    assert "domain" in data[0]
    assert "label" in data[0]


def test_telemetry_synthetic_generation():
    mock_intermediate = [
        {"url": "https://doubleclick.net/ad", "domain": "doubleclick.net", "label": "advertising", "request_type": "image", "third_party": 1},
        {"url": "https://google.com/search", "domain": "google.com", "label": "safe", "request_type": "document", "third_party": 0}
    ]
    
    telemetry = generate_synthetic_telemetry(mock_intermediate)
    
    assert len(telemetry) == 2
    assert telemetry[0]["domain"] == "doubleclick.net"
    assert telemetry[0]["label"] == "advertising"
    assert "request_frequency" in telemetry[0]
    assert "timestamp" in telemetry[0]
