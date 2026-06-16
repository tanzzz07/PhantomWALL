import os
import sys
import json
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.evaluator import calculate_metrics


def test_calculate_metrics():
    # Setup mock classifier
    clf = RandomForestClassifier(n_estimators=5, random_state=42)
    
    # Simple data
    X = np.random.rand(10, 5)
    y = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    clf.fit(X, y)
    
    metrics = calculate_metrics(clf, X, y, num_classes=2)
    
    assert "accuracy" in metrics
    assert "f1_macro" in metrics
    assert "inference_time_ms" in metrics
    assert "confusion_matrix" in metrics
    
    assert isinstance(metrics["accuracy"], float)
    assert len(metrics["confusion_matrix"]) == 2
