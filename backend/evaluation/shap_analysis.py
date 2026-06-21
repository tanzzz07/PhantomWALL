import os
import sys
import json
import logging
import joblib
from pathlib import Path
import pandas as pd
import numpy as np

# Headless matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Resolve path for backend imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def run_fallback_importance(model, feature_names):
    """Fallback to standard feature importances using matplotlib if SHAP is unavailable."""
    logger.info("Running standard Gini feature importance fallback...")
    
    # Extract importances based on model type
    importance = None
    if hasattr(model, "feature_importances_"):
        importance = model.feature_importances_
    elif hasattr(model, "coef_"):
        # For Logistic Regression, average absolute coefficients across classes
        importance = np.mean(np.abs(model.coef_), axis=0)
        
    if importance is None:
        logger.warning("Could not extract feature importances. Saving blank plots.")
        importance = np.zeros(len(feature_names))

    # Sort importances
    indices = np.argsort(importance)[::-1]
    sorted_features = [feature_names[i] for i in indices]
    sorted_importances = importance[indices]

    # Save feature_importance.png
    plt.figure(figsize=(12, 8))
    plt.barh(sorted_features[:15], sorted_importances[:15], color="skyblue")
    plt.gca().invert_yaxis()
    plt.title("Top 15 Feature Importances (Gini/Coefficients)")
    plt.xlabel("Importance Score")
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "feature_importance.png", dpi=150)
    plt.close()
    logger.info("Saved feature_importance.png (Fallback)")

    # Save shap_summary.png (as duplicate of importance plot or text plot)
    plt.figure(figsize=(12, 8))
    plt.barh(sorted_features[:15], sorted_importances[:15], color="purple")
    plt.gca().invert_yaxis()
    plt.title("Feature Impact Summary (Gini Fallback)")
    plt.xlabel("Importance Score")
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=150)
    plt.close()
    logger.info("Saved shap_summary.png (Fallback)")

    # Save shap_bar_plot.png
    plt.figure(figsize=(12, 8))
    plt.bar(sorted_features[:10], sorted_importances[:10], color="green")
    plt.xticks(rotation=45, ha="right")
    plt.title("Top 10 Feature Contributions (Gini Fallback)")
    plt.ylabel("Importance Score")
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "shap_bar_plot.png", dpi=150)
    plt.close()
    logger.info("Saved shap_bar_plot.png (Fallback)")


def run_shap_analysis():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting explainability pipeline...")
    
    # 1. Load best model
    model_path = MODELS_DIR / "phantomwall_model.pkl"
    if not model_path.exists():
        logger.error(f"Best model not found at {model_path}. Run evaluator.py first.")
        return
        
    model = joblib.load(model_path)
    
    # 2. Load feature schema
    schema_path = MODELS_DIR / "feature_schema.json"
    if not schema_path.exists():
        logger.error(f"Feature schema not found at {schema_path}.")
        return
    with open(schema_path, "r", encoding="utf-8") as f:
        feature_names = json.load(f)
        
    # 3. Load dataset samples to use as background data
    split_path = MODELS_DIR / "train_test_split.pkl"
    if not split_path.exists():
        logger.error(f"Train/test split not found at {split_path}.")
        return
    split_data = joblib.load(split_path)
    X_test = split_data["X_test"][feature_names]
    
    # 4. Try to import and run SHAP
    try:
        import shap
        logger.info("SHAP package imported successfully. Running SHAP analysis...")
        
        # XGBoost or RF can use TreeExplainer
        if model.__class__.__name__ in ["XGBClassifier", "RandomForestClassifier"]:
            explainer = shap.TreeExplainer(model)
            # Use a sample of 200 items for speed
            sample_data = X_test.head(200)
            shap_values = explainer.shap_values(sample_data)
            
            # Save shap_summary.png
            plt.figure(figsize=(12, 8))
            shap.summary_plot(shap_values, sample_data, show=False)
            plt.title("SHAP Summary Plot")
            plt.tight_layout()
            plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=150)
            plt.close()
            logger.info("Saved shap_summary.png")
            
            # Save shap_bar_plot.png
            plt.figure(figsize=(12, 8))
            shap.summary_plot(shap_values, sample_data, plot_type="bar", show=False)
            plt.title("SHAP Bar Plot")
            plt.tight_layout()
            plt.savefig(REPORTS_DIR / "shap_bar_plot.png", dpi=150)
            plt.close()
            logger.info("Saved shap_bar_plot.png")
            
            # Generate feature_importance.png (using explainer or fallback)
            run_fallback_importance(model, feature_names)
        else:
            # Fallback for linear models or others
            explainer = shap.Explainer(model, X_test.head(50))
            shap_values = explainer(X_test.head(200))
            
            plt.figure(figsize=(12, 8))
            shap.plots.beeswarm(shap_values, show=False)
            plt.title("SHAP Summary Plot")
            plt.tight_layout()
            plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=150)
            plt.close()
            logger.info("Saved shap_summary.png")
            
            plt.figure(figsize=(12, 8))
            shap.plots.bar(shap_values, show=False)
            plt.title("SHAP Bar Plot")
            plt.tight_layout()
            plt.savefig(REPORTS_DIR / "shap_bar_plot.png", dpi=150)
            plt.close()
            logger.info("Saved shap_bar_plot.png")
            
            run_fallback_importance(model, feature_names)
            
    except Exception as e:
        logger.warning(f"SHAP analysis encountered an error or was not installed: {e}")
        # Run standard fallback
        run_fallback_importance(model, feature_names)


if __name__ == "__main__":
    run_shap_analysis()
