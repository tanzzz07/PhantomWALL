import logging
import json
import pandas as pd
import numpy as np
from inference.predictor import Predictor

logger = logging.getLogger(__name__)

# Feature name to human readable description mapping
FEATURE_EXPLANATION_MAP = {
    "third_party_flag": "it originated from a third-party domain",
    "fingerprinting_keyword_score": "matched fingerprinting indicators and keywords",
    "advertising_keyword_score": "matched advertising keywords and patterns",
    "analytics_keyword_score": "matched analytics and event tracking indicators",
    "tracker_keyword_score": "matched general tracker signatures",
    "tracking_pattern_score": "matched specific query tracking parameter signatures",
    "request_frequency": "exhibited high request frequency during the session",
    "session_occurrence_count": "appeared repeatedly during the browsing session",
    "entropy": "the request domain had high complexity and entropy",
    "tld_risk_score": "the domain used a high-risk top-level domain extension",
    "url_length": "the request URL was exceptionally long",
    "query_parameter_count": "it passed multiple query parameters",
    "query_parameter_length": "it had long query parameters",
    "path_depth": "the URL path depth was deep",
    "digit_ratio": "the domain contained a high ratio of digits",
    "hyphen_count": "the domain name contained hyphens",
    "special_character_count": "the URL contained many special characters",
    "request_type": "of its specific resource type context",
    "referrer_domain_similarity": "its domain was highly dissimilar to the referrer",
    "suspicious_character_count": "the URL contained suspicious characters",
    "encoded_character_ratio": "the URL had a high ratio of encoded characters",
    "high_entropy_subdomain": "the subdomain had unusually high entropy"
}


class ExplanationService:
    """Provides Explainable AI (XAI) details using SHAP or heuristic fallbacks."""

    @classmethod
    def generate_explanation(
        cls,
        raw_features: dict,
        classification: str,
        confidence: float
    ) -> tuple[list[str], str]:
        """
        Generate top features list and human-readable explanation.
        Returns:
            top_features: list of feature names (strings)
            explanation: human-readable explanation string
        """
        top_features = []
        predictor = Predictor()

        # 1. Try to use SHAP if model is loaded and shap package is available
        if predictor.model_loaded and predictor.model is not None:
            try:
                import shap
                
                # Convert raw features to dataframe and reorder columns
                df = pd.DataFrame([raw_features])
                df = df[predictor.feature_names]
                
                # Find class index
                pred_idx = 0
                if predictor.label_encoder is not None:
                    try:
                        classes_lower = [c.lower() for c in predictor.label_encoder.classes_]
                        if classification.lower() in classes_lower:
                            pred_idx = classes_lower.index(classification.lower())
                    except Exception:
                        pass
                
                # Compute SHAP values
                explainer = shap.TreeExplainer(predictor.model)
                shap_values = explainer(df)
                
                if hasattr(shap_values, "values"):
                    values = shap_values.values
                else:
                    values = shap_values
                
                # Parse multiclass SHAP values
                if len(values.shape) == 3:  # (samples, features, classes)
                    contributions = values[0, :, pred_idx]
                elif len(values.shape) == 2:  # (samples, features)
                    contributions = values[0, :]
                else:
                    contributions = values
                
                # Pair with feature names and sort by absolute contribution descending
                feat_contribs = list(zip(predictor.feature_names, contributions))
                feat_contribs.sort(key=lambda x: abs(x[1]), reverse=True)
                
                # Extract top 3 features
                top_features = [item[0] for item in feat_contribs[:3]]
                logger.info(f"SHAP explanation generated successfully. Top features: {top_features}")
                
            except Exception as e:
                logger.warning(f"SHAP computation failed or library not available: {e}. Falling back to rules.")
        
        # 2. Fallback to heuristic feature scoring if SHAP fails or model is not loaded
        if not top_features:
            top_features = cls._heuristic_top_features(raw_features)
            logger.info(f"Heuristic fallback explanation generated. Top features: {top_features}")

        # 3. Generate human readable explanation string
        explanation_clauses = []
        for feat in top_features:
            clause = FEATURE_EXPLANATION_MAP.get(feat)
            if clause:
                explanation_clauses.append(clause)
        
        if not explanation_clauses:
            explanation_clauses = ["its behavioral attributes matched typical indicators"]

        if len(explanation_clauses) == 3:
            explanation_str = (
                f"This request was classified as {classification} because "
                f"{explanation_clauses[0]}, {explanation_clauses[1]}, and {explanation_clauses[2]}."
            )
        elif len(explanation_clauses) == 2:
            explanation_str = (
                f"This request was classified as {classification} because "
                f"{explanation_clauses[0]} and {explanation_clauses[1]}."
            )
        else:
            explanation_str = (
                f"This request was classified as {classification} because "
                f"{explanation_clauses[0]}."
            )
            
        return top_features, explanation_str

    @classmethod
    def _heuristic_top_features(cls, raw_features: dict) -> list[str]:
        """Compute heuristic importance scores to determine top 3 features."""
        scores = {}
        for feat, val in raw_features.items():
            try:
                numeric_val = float(val) if val is not None else 0.0
            except ValueError:
                numeric_val = 0.0

            # Assign weights to features to simulate model importance
            if feat == "third_party_flag":
                scores[feat] = numeric_val * 1.5
            elif feat == "fingerprinting_keyword_score":
                scores[feat] = numeric_val * 2.0
            elif feat == "advertising_keyword_score":
                scores[feat] = numeric_val * 1.8
            elif feat == "analytics_keyword_score":
                scores[feat] = numeric_val * 1.6
            elif feat == "tracker_keyword_score":
                scores[feat] = numeric_val * 1.5
            elif feat == "tracking_pattern_score":
                scores[feat] = numeric_val * 2.0
            elif feat == "tld_risk_score":
                scores[feat] = numeric_val * 1.2
            elif feat == "request_frequency":
                scores[feat] = (numeric_val / 5.0) * 1.0
            elif feat == "session_occurrence_count":
                scores[feat] = (numeric_val / 5.0) * 0.9
            elif feat == "entropy":
                scores[feat] = (numeric_val - 3.0) * 0.5 if numeric_val > 3.0 else 0.0
            elif feat == "url_length":
                scores[feat] = (numeric_val / 150.0) * 0.4
            elif feat == "query_parameter_count":
                scores[feat] = numeric_val * 0.3
            elif feat == "special_character_count":
                scores[feat] = (numeric_val / 10.0) * 0.2
            else:
                scores[feat] = numeric_val * 0.1

        # Sort features by score descending
        sorted_feats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_feats[:3]]
