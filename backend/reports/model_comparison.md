# Model Comparison & Selection Report

The pipeline evaluated three models. The primary optimization metric is **Macro F1 Score**.

## Summary Metrics Table

| Model | Accuracy | Precision (Macro) | Recall (Macro) | Macro F1 | Weighted F1 | ROC-AUC | Avg Inference (ms) | Size (KB) |
|---|---|---|---|---|---|---|---|---|
| Logistic Regression | 0.9548 | 0.9509 | 0.9257 | **0.9374** | 0.9539 | 0.9954 | 0.0256 | 2.6 |
| Random Forest | 0.9761 | 0.9794 | 0.9497 | **0.9629** | 0.9754 | 0.9980 | 0.0201 | 6113.8 |
| XGBoost | 0.9801 | 0.9762 | 0.9680 | **0.9720** | 0.9799 | 0.9988 | 0.0126 | 880.1 |

## Strengths & Weaknesses Analysis

### 1. Logistic Regression
- **Strengths**: Lightweight, extremely fast inference, highly interpretable coefficients.
- **Weaknesses**: Struggles with non-linear relationships and interactions between features.

### 2. Random Forest
- **Strengths**: Robust to overfitting, handles categorical encoders/integers natively, easy feature importances.
- **Weaknesses**: Larger file size, slightly slower inference compared to simpler structures.

### 3. XGBoost
- **Strengths**: Exceptional classification accuracy, highly optimized tree boosting, handles missing values, efficient runtime.
- **Weaknesses**: Requires tuning of learning rate and tree parameters to prevent overfitting.

## Final Recommendation

**Winner**: `XGBoost`

We deploy `XGBoost` as the default model due to its superior Macro F1 score (0.9720) and efficient performance profile.

## Confusion Matrices

### Logistic Regression
```text
Labels order: advertising, analytics, fingerprinting, safe, suspicious
 590     0     0     0    10
   0   589    11     0     0
   0    24    86     0     0
   0     0     0     1     0
  23     0     0     0   171
```

### Random Forest
```text
Labels order: advertising, analytics, fingerprinting, safe, suspicious
 597     1     0     0     2
   0   596     4     0     0
   0    23    87     0     0
   0     0     0     1     0
   6     0     0     0   188
```

### XGBoost
```text
Labels order: advertising, analytics, fingerprinting, safe, suspicious
 595     1     0     0     4
   0   593     7     0     0
   0    12    98     0     0
   0     0     0     1     0
   6     0     0     0   188
```

