import os
import sys
import json
import time
import logging
import joblib
import shutil
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
)

# Resolve path for backend imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_metrics(model, X_test, y_test, num_classes) -> dict:
    """Evaluate a model on various classification metrics."""
    # 1. Predictions & Probabilities
    start_time = time.perf_counter()
    y_pred = model.predict(X_test)
    inference_time = (time.perf_counter() - start_time) / len(X_test) * 1000  # ms per sample
    
    y_prob = model.predict_proba(X_test)

    # 2. Score metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision_macro = precision_score(y_test, y_pred, average="macro", zero_division=0)
    recall_macro = recall_score(y_test, y_pred, average="macro", zero_division=0)
    f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)
    f1_weighted = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    
    # 3. Conf matrix
    cm = confusion_matrix(y_test, y_pred)
    
    # 4. ROC-AUC One-vs-Rest
    try:
        roc_auc = roc_auc_score(y_test, y_prob, multi_class="ovr", average="macro")
    except Exception as e:
        logger.warning(f"Failed to calculate ROC-AUC: {e}")
        roc_auc = 0.0

    return {
        "accuracy": accuracy,
        "precision_macro": precision_macro,
        "recall_macro": recall_macro,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
        "roc_auc": roc_auc,
        "inference_time_ms": inference_time,
        "confusion_matrix": cm.tolist()
    }


def run_evaluation():
    ensure_dirs()
    logger.info("Evaluating trained models...")
    
    # Load test split
    split_path = MODELS_DIR / "train_test_split.pkl"
    if not split_path.exists():
        logger.error(f"Train/test split not found at {split_path}. Run trainer.py first.")
        return
        
    split_data = joblib.load(split_path)
    X_test = split_data["X_test"]
    y_test = np.array(split_data["y_test"])
    
    # Load label encoder to get names
    le_path = MODELS_DIR / "label_encoder.pkl"
    if le_path.exists():
        le = joblib.load(le_path)
        class_names = le.classes_.tolist()
    else:
        class_names = [str(i) for i in np.unique(y_test)]
        
    num_classes = len(class_names)
    
    # Find trained models
    model_paths = {
        "Logistic Regression": MODELS_DIR / "logistic_regression.pkl",
        "Random Forest": MODELS_DIR / "random_forest.pkl",
        "XGBoost": MODELS_DIR / "xgboost.pkl"
    }
    
    comparison_results = {}
    
    for name, path in model_paths.items():
        if not path.exists():
            logger.warning(f"Model {name} not found at {path}. Skipping.")
            continue
            
        model = joblib.load(path)
        logger.info(f"Evaluating {name}...")
        
        # Calculate size/memory
        file_size_kb = path.stat().st_size / 1024.0
        
        metrics = calculate_metrics(model, X_test, y_test, num_classes)
        metrics["file_size_kb"] = file_size_kb
        
        comparison_results[name] = metrics

    if not comparison_results:
        logger.error("No models were successfully evaluated.")
        return

    # Select the best model based on Macro F1
    best_model_name = max(comparison_results, key=lambda k: comparison_results[k]["f1_macro"])
    logger.info(f"Selected best model: {best_model_name} with Macro F1: {comparison_results[best_model_name]['f1_macro']:.4f}")
    
    # Export best model
    best_model_path = model_paths[best_model_name]
    final_model_dest = MODELS_DIR / "phantomwall_model.pkl"
    shutil.copy(best_model_path, final_model_dest)
    logger.info(f"Exported final model to {final_model_dest}")
    
    # Write model_metadata.json
    metadata = {
        "algorithm": best_model_name,
        "version": "1.0",
        "macro_f1": float(comparison_results[best_model_name]["f1_macro"]),
        "accuracy": float(comparison_results[best_model_name]["accuracy"]),
        "inference_time_ms": float(comparison_results[best_model_name]["inference_time_ms"]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    with open(MODELS_DIR / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved model_metadata.json")

    # Generate model_comparison.md report
    report_content = "# Model Comparison & Selection Report\n\n"
    report_content += f"The pipeline evaluated three models. The primary optimization metric is **Macro F1 Score**.\n\n"
    
    report_content += "## Summary Metrics Table\n\n"
    report_content += "| Model | Accuracy | Precision (Macro) | Recall (Macro) | Macro F1 | Weighted F1 | ROC-AUC | Avg Inference (ms) | Size (KB) |\n"
    report_content += "|---|---|---|---|---|---|---|---|---|\n"
    
    for name, r in comparison_results.items():
        report_content += (
            f"| {name} | {r['accuracy']:.4f} | {r['precision_macro']:.4f} | {r['recall_macro']:.4f} | "
            f"**{r['f1_macro']:.4f}** | {r['f1_weighted']:.4f} | {r['roc_auc']:.4f} | "
            f"{r['inference_time_ms']:.4f} | {r['file_size_kb']:.1f} |\n"
        )
        
    report_content += "\n## Strengths & Weaknesses Analysis\n\n"
    
    # Logistic Regression
    report_content += "### 1. Logistic Regression\n"
    report_content += "- **Strengths**: Lightweight, extremely fast inference, highly interpretable coefficients.\n"
    report_content += "- **Weaknesses**: Struggles with non-linear relationships and interactions between features.\n\n"
    
    # Random Forest
    report_content += "### 2. Random Forest\n"
    report_content += "- **Strengths**: Robust to overfitting, handles categorical encoders/integers natively, easy feature importances.\n"
    report_content += "- **Weaknesses**: Larger file size, slightly slower inference compared to simpler structures.\n\n"
    
    # XGBoost
    report_content += "### 3. XGBoost\n"
    report_content += "- **Strengths**: Exceptional classification accuracy, highly optimized tree boosting, handles missing values, efficient runtime.\n"
    report_content += "- **Weaknesses**: Requires tuning of learning rate and tree parameters to prevent overfitting.\n\n"
    
    report_content += "## Final Recommendation\n\n"
    report_content += f"**Winner**: `{best_model_name}`\n\n"
    report_content += f"We deploy `{best_model_name}` as the default model due to its superior Macro F1 score "
    report_content += f"({comparison_results[best_model_name]['f1_macro']:.4f}) and efficient performance profile.\n\n"
    
    # Append confusion matrices
    report_content += "## Confusion Matrices\n\n"
    for name, r in comparison_results.items():
        report_content += f"### {name}\n"
        report_content += "```text\n"
        report_content += "Labels order: " + ", ".join(class_names) + "\n"
        matrix_str = "\n".join(["  ".join([f"{val:4d}" for val in row]) for row in r["confusion_matrix"]])
        report_content += matrix_str + "\n"
        report_content += "```\n\n"

    with open(REPORTS_DIR / "model_comparison.md", "w", encoding="utf-8") as f:
        f.write(report_content)
    logger.info("Saved model_comparison.md")


if __name__ == "__main__":
    run_evaluation()
