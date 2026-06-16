from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from urllib.parse import urlparse

from inference.predictor import Predictor
from app.services.classifier import TrackerClassifier

router = APIRouter(tags=["predict"])


class PredictIn(BaseModel):
    url: str = Field(..., example="https://tracker.example.com/pixel")
    request_type: str = Field("other", example="script")
    third_party: bool = Field(True, example=True)
    request_frequency: int = Field(1, example=1)
    referrer_domain: str = Field("", example="https://referrer.example.com")


class PredictResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: dict[str, float]


@router.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_threat(payload: PredictIn) -> PredictResponse:
    """Classify a network request using the trained ML model or the handcrafted fallback."""
    predictor = Predictor()
    
    # 1. Attempt ML prediction
    if predictor.model_loaded:
        result = predictor.predict(
            url=payload.url,
            request_type=payload.request_type,
            third_party=payload.third_party,
            request_frequency=payload.request_frequency,
            referrer_domain=payload.referrer_domain
        )
        if result:
            return PredictResponse(
                prediction=result["prediction"],
                confidence=result["confidence"],
                probabilities=result["probabilities"]
            )
            
    # 2. Rule-based fallback if ML model is not trained/loaded
    logger_name = "app.api.routes.predict"
    import logging
    logger = logging.getLogger(logger_name)
    logger.info("ML predictor not loaded; falling back to handcrafted rule-based classifier.")
    
    try:
        parsed = urlparse(payload.url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        if ":" in domain:
            domain = domain.split(":")[0]
    except Exception:
        domain = payload.url
        
    rule_class = TrackerClassifier.classify(
        domain=domain,
        url=payload.url,
        recent_count=payload.request_frequency,
        is_third_party=payload.third_party
    )
    
    # Map rule-based output class to ML output classes
    # Rule classes: Fingerprinting, Advertising, Analytics, Tracker, Safe
    class_map = {
        "fingerprinting": "Fingerprinting",
        "advertising": "Advertising",
        "analytics": "Analytics",
        "tracker": "Suspicious",
        "safe": "Safe"
    }
    
    final_pred = class_map.get(rule_class.lower(), "Safe")
    
    # Synthesize probabilities based on classification
    probs = {
        "Safe": 0.0,
        "Analytics": 0.0,
        "Advertising": 0.0,
        "Fingerprinting": 0.0,
        "Suspicious": 0.0
    }
    probs[final_pred] = 1.0
    
    return PredictResponse(
        prediction=final_pred,
        confidence=1.0,
        probabilities=probs
    )
