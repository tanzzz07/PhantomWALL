import os
import json
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Set headless mode for matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "final" / "phantomwall_dataset.csv"


def ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_analysis():
    ensure_dirs()
    logger.info("Starting dataset analysis...")
    
    if not DATASET_PATH.exists():
        logger.error(f"Dataset CSV not found at {DATASET_PATH}. Run extractor.py first.")
        return

    # Load dataset
    df = pd.read_csv(DATASET_PATH)
    logger.info(f"Loaded dataset with shape: {df.shape}")

    # 1. Dataset Metadata JSON
    metadata = {
        "dataset_version": "v1",
        "samples": int(df.shape[0]),
        "features": int(df.shape[1] - 1),  # Exclude label
        "classes": int(df["label"].nunique())
    }
    with open(REPORTS_DIR / "dataset_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved dataset_metadata.json")

    # 2. Class Distribution Report & Plot
    class_counts = df["label"].value_counts()
    class_pct = df["label"].value_counts(normalize=True) * 100
    
    stats_content = "# Dataset Statistics\n\n"
    stats_content += "## Overview\n"
    stats_content += f"- **Total Samples**: {df.shape[0]}\n"
    stats_content += f"- **Number of Features**: {df.shape[1] - 1}\n"
    stats_content += f"- **Number of Classes**: {df['label'].nunique()}\n\n"
    stats_content += "## Class Distribution\n\n"
    stats_content += "| Class | Count | Percentage |\n"
    stats_content += "|---|---|---|\n"
    for label, count in class_counts.items():
        pct = class_pct[label]
        stats_content += f"| {label} | {count} | {pct:.2f}% |\n"
    
    with open(REPORTS_DIR / "dataset_statistics.md", "w", encoding="utf-8") as f:
        f.write(stats_content)
    logger.info("Saved dataset_statistics.md")

    # Generate Class Distribution plot
    plt.figure(figsize=(8, 5))
    sns.barplot(x=class_counts.index, y=class_counts.values, palette="viridis")
    plt.title("Class Distribution in PhantomWALL Dataset")
    plt.xlabel("Category")
    plt.ylabel("Number of Samples")
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "class_distribution.png", dpi=150)
    plt.close()
    logger.info("Saved class_distribution.png")

    # 3. Missing Values Report
    missing = df.isnull().sum()
    missing_pct = (df.isnull().sum() / len(df)) * 100
    
    missing_content = "# Missing Values Report\n\n"
    if missing.sum() == 0:
        missing_content += "No missing values found in the dataset! It is 100% complete.\n"
    else:
        missing_content += "| Column | Missing Count | Missing Percentage |\n"
        missing_content += "|---|---|---|\n"
        for col, val in missing.items():
            if val > 0:
                missing_content += f"| {col} | {val} | {missing_pct[col]:.2f}% |\n"
                
    with open(REPORTS_DIR / "missing_values_report.md", "w", encoding="utf-8") as f:
        f.write(missing_content)
    logger.info("Saved missing_values_report.md")

    # 4. Duplicate Analysis Report
    duplicates_count = df.duplicated().sum()
    duplicate_pct = (duplicates_count / len(df)) * 100
    
    duplicate_content = "# Duplicate Analysis Report\n\n"
    duplicate_content += f"- **Total Duplicated Rows**: {duplicates_count}\n"
    duplicate_content += f"- **Duplicate Ratio**: {duplicate_pct:.2f}%\n\n"
    if duplicates_count > 0:
        duplicate_content += "Duplicate rows exist due to exact overlap in static rules or telemetry patterns. "
        duplicate_content += "These will be handled appropriately during split or training.\n"
        
    with open(REPORTS_DIR / "duplicate_analysis.md", "w", encoding="utf-8") as f:
        f.write(duplicate_content)
    logger.info("Saved duplicate_analysis.md")

    # 5. Feature Summary Report
    desc = df.describe().T
    feature_content = "# Feature Summary Report\n\n"
    feature_content += "Statistical metrics of numeric features:\n\n"
    feature_content += "| Feature | Mean | Std Dev | Min | 50% (Median) | Max |\n"
    feature_content += "|---|---|---|---|---|---|\n"
    for idx, row in desc.iterrows():
        feature_content += f"| {idx} | {row['mean']:.4f} | {row['std']:.4f} | {row['min']:.4f} | {row['50%']:.4f} | {row['max']:.4f} |\n"
        
    with open(REPORTS_DIR / "feature_summary.md", "w", encoding="utf-8") as f:
        f.write(feature_content)
    logger.info("Saved feature_summary.md")

    # 6. Correlation Matrix Heatmap
    # Select only numeric features for correlation
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    corr = df[numeric_cols].corr()
    
    plt.figure(figsize=(16, 12))
    sns.heatmap(corr, annot=False, cmap="coolwarm", fmt=".2f", linewidths=0.5, vmin=-1.0, vmax=1.0)
    plt.title("Feature Correlation Matrix", fontsize=16)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "correlation_matrix.png", dpi=150)
    plt.close()
    logger.info("Saved correlation_matrix.png")
    
    logger.info("Dataset analysis completed successfully!")


if __name__ == "__main__":
    run_analysis()
