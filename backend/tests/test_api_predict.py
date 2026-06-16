import os
import sys

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set dummy env variables
os.environ["PHANTOMWALL_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PHANTOMWALL_JWT_SECRET_KEY"] = "dummy-secret-key-12345678901234567890"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_predict_endpoint_success():
    payload = {
        "url": "https://www.google-analytics.com/g/collect?v=2",
        "request_type": "script",
        "third_party": True
    }
    
    response = client.post("/predict", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "prediction" in data
    assert "confidence" in data
    assert "probabilities" in data
    
    # Assert validation structure
    assert isinstance(data["prediction"], str)
    assert isinstance(data["confidence"], float)
    assert isinstance(data["probabilities"], dict)
    assert "Safe" in data["probabilities"]
    assert "Analytics" in data["probabilities"]
