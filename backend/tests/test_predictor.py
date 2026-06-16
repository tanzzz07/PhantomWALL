import os
import sys

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from inference.predictor import Predictor


def test_predictor_singleton():
    p1 = Predictor()
    p2 = Predictor()
    assert p1 is p2


def test_predict_not_loaded():
    predictor = Predictor()
    # If model is not loaded, it should return None or handle it gracefully
    if not predictor.model_loaded:
        res = predictor.predict(
            url="https://example.com",
            request_type="script",
            third_party=True
        )
        assert res is None
