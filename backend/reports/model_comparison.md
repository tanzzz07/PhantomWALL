# Model Comparison & Selection Report

The pipeline evaluated three models. The primary optimization metric is **Macro F1 Score**.

## Summary Metrics Table

| Model | Accuracy | Precision (Macro) | Recall (Macro) | Macro F1 | Weighted F1 | ROC-AUC | Avg Inference (ms) | Size (KB) |
|---|---|---|---|---|---|---|---|---|
| Logistic Regression | 0.9002 | 0.9011 | 0.9001 | **0.9002** | 0.9003 | 0.9834 | 0.0218 | 2.6 |
| Random Forest | 0.9318 | 0.9327 | 0.9317 | **0.9321** | 0.9321 | 0.9919 | 0.0260 | 11741.7 |
| XGBoost | 0.9447 | 0.9452 | 0.9447 | **0.9447** | 0.9448 | 0.9951 | 0.0186 | 1353.4 |

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

We deploy `XGBoost` as the default model due to its superior Macro F1 score (0.9447) and efficient performance profile.

## Confusion Matrices

### Logistic Regression
```text
Labels order: advertising, analytics, fingerprinting, safe, suspicious
 271     4     0     0     4
  16   220     0     7    35
   3     9   261     2     4
   0    12     0   261     6
   0    23     0    14   241
```

### Random Forest
```text
Labels order: advertising, analytics, fingerprinting, safe, suspicious
 270     7     1     0     1
  13   241     2     3    19
   3    11   264     0     1
   0     4     0   272     3
   0    24     0     3   251
```

### XGBoost
```text
Labels order: advertising, analytics, fingerprinting, safe, suspicious
 270     5     2     0     2
  12   246     1     1    18
   3    10   263     0     3
   0     1     0   275     3
   1    12     0     3   262
```

