import os
import sys
import json
import logging
import joblib
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
# Resolve path for backend imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "final" / "phantomwall_dataset.csv"

# Fixed mapping for request_type to keep encoding robust and lightweight
REQUEST_TYPE_MAP = {
    "script": 0,
    "image": 1,
    "xmlhttprequest": 2,
    "sub_frame": 3,
    "stylesheet": 4,
    "document": 5,
    "other": 6
}


def ensure_dirs():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def preprocess_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list, LabelEncoder]:
    """Encode labels and categorical columns, dropping unused raw text columns."""
    df = df.copy()
    
    # 1. Encode Target labels
    le = LabelEncoder()
    y = le.fit_transform(df["label"])
    
    # 2. Encode request_type to integer using static map
    df["request_type"] = df["request_type"].str.lower().map(REQUEST_TYPE_MAP).fillna(REQUEST_TYPE_MAP["other"]).astype(int)
    
    # 3. Drop non-numeric/raw text features
    X = df.drop(columns=["label", "tld"], errors="ignore")
    
    # 4. Save feature schema columns
    feature_names = X.columns.tolist()
    
    return X, pd.Series(y), feature_names, le


def train_models():
    ensure_dirs()
    logger.info("Starting model training pipeline...")
    
    if not DATA_PATH.exists():
        logger.error(f"Dataset path {DATA_PATH} does not exist. Run extractor.py first.")
        return
        
    df = pd.read_csv(DATA_PATH)
    logger.info(f"Loaded dataset with shape {df.shape}")
    
    # Preprocess
    X, y, feature_names, label_encoder = preprocess_data(df)
    
    # Save label encoder and feature schema immediately
    joblib.dump(label_encoder, MODELS_DIR / "label_encoder.pkl")
    with open(MODELS_DIR / "feature_schema.json", "w", encoding="utf-8") as f:
        json.dump(feature_names, f, indent=2)
    logger.info("Saved label_encoder.pkl and feature_schema.json")
    
    # Stratified Train/Test Split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    logger.info(f"Train set shape: {X_train.shape}, Test set shape: {X_test.shape}")
    
    # 1. Logistic Regression
    logger.info("Training Logistic Regression...")

    lr = LogisticRegression(
        max_iter=3000,
        random_state=42
    )

    lr.fit(X_train, y_train)

    # 2. Random Forest
    logger.info("Training Random Forest...")

    best_rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=2,
        random_state=42,
        n_jobs=2
    )

    best_rf.fit(X_train, y_train)

    logger.info("Random Forest training completed.")

    # 3. XGBoost
    logger.info("Training XGBoost...")

    best_xgb = xgb.XGBClassifier(
        objective="multi:softprob",
        learning_rate=0.1,
        max_depth=5,
        subsample=0.8,
        n_estimators=100,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=2
    )

    best_xgb.fit(X_train, y_train)

    logger.info("XGBoost training completed.")
    joblib.dump(lr, MODELS_DIR / "logistic_regression.pkl")
    joblib.dump(best_rf, MODELS_DIR / "random_forest.pkl")
    joblib.dump(best_xgb, MODELS_DIR / "xgboost.pkl")
    
    # Save train/test datasets for evaluation script
    train_test_data = {
        "X_train": X_train.to_dict(),
        "X_test": X_test.to_dict(),
        "y_train": y_train.tolist(),
        "y_test": y_test.tolist()
    }
    with open(MODELS_DIR / "train_test_split.json", "w", encoding="utf-8") as f:
        json.dump(train_test_data, f)
        
    logger.info("Models trained and exported successfully!")


if __name__ == "__main__":
    train_models()
