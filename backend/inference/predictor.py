import os
import sys
import json
import logging
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from threading import Lock

# Resolve path for backend imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from feature_engineering.extractor import FeatureExtractor
from training.trainer import REQUEST_TYPE_MAP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


class Predictor:
    """Thread-safe prediction service for PhantomWALL ML Threat Classification."""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance.initialized = False
            return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        self.model = None
        self.label_encoder = None
        self.feature_names = None
        self.metadata = None
        self.model_loaded = False
        
        self.load_model()
        self.initialized = True

    def load_model(self):
        """Load the model and supporting artifacts from models directory."""
        model_path = MODELS_DIR / "phantomwall_model.pkl"
        le_path = MODELS_DIR / "label_encoder.pkl"
        schema_path = MODELS_DIR / "feature_schema.json"
        meta_path = MODELS_DIR / "model_metadata.json"
        
        if not (model_path.exists() and le_path.exists() and schema_path.exists()):
            logger.warning(
                f"ML model artifacts missing at {MODELS_DIR}. Run training pipeline first."
            )
            return
            
        try:
            self.model = joblib.load(model_path)
            self.label_encoder = joblib.load(le_path)
            with open(schema_path, "r", encoding="utf-8") as f:
                self.feature_names = json.load(f)
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                    
            self.model_loaded = True
            logger.info(
                f"Successfully loaded final model ({self.metadata.get('algorithm', 'Unknown') if self.metadata else 'Unknown'}) "
                f"with Macro F1: {self.metadata.get('macro_f1', 0.0) if self.metadata else 0.0:.4f}"
            )
        except Exception as e:
            logger.error(f"Error loading model artifacts: {e}")
            self.model_loaded = False

    def predict(
        self,
        url: str,
        request_type: str,
        third_party: bool | int,
        request_frequency: int = 1,
        referrer_domain: str = ""
    ) -> dict | None:
        """Perform thread-safe inference on a request event."""
        if not self.model_loaded:
            return None
            
        try:
            # 1. Feature extraction
            raw_features = FeatureExtractor.extract_features(
                url=url,
                request_type=request_type,
                third_party=third_party,
                request_frequency=request_frequency,
                referrer_domain=referrer_domain,
                session_occurrence_count=request_frequency
            )
            
            # 2. Encode categorical variables using the trainer mappings
            raw_features["request_type"] = REQUEST_TYPE_MAP.get(
                raw_features["request_type"].lower(), 
                REQUEST_TYPE_MAP["other"]
            )
            
            # 3. Create DataFrame and reorder columns
            df = pd.DataFrame([raw_features])
            df = df[self.feature_names]
            
            # 4. Predict
            with self._lock:
                pred_idx = self.model.predict(df)[0]
                probabilities = self.model.predict_proba(df)[0]
                
            # Decode predictions
            pred_class = self.label_encoder.classes_[pred_idx]
            
            # Map labels to Capitalized format for schema output
            # target classes: safe, analytics, advertising, fingerprinting, suspicious
            class_map = {
                "safe": "Safe",
                "analytics": "Analytics",
                "advertising": "Advertising",
                "fingerprinting": "Fingerprinting",
                "suspicious": "Suspicious"
            }
            
            pred_class_cap = class_map.get(pred_class, "Safe")
            confidence = float(probabilities[pred_idx])
            
            probs_dict = {
                class_map.get(cls_name, cls_name.capitalize()): float(prob)
                for cls_name, prob in zip(self.label_encoder.classes_, probabilities)
            }
            
            return {
                "prediction": pred_class_cap,
                "confidence": confidence,
                "probabilities": probs_dict
            }
        except Exception as e:
            logger.error(f"Inference prediction failed: {e}")
            return None
