import math
import re
from collections import Counter
from urllib.parse import urlparse, parse_qsl


class TrackerClassifier:
    """Mathematical linear classifier for labeling network requests."""

    CLASSES = ["Fingerprinting", "Advertising", "Analytics", "Tracker", "Safe"]

    # Linear weights for the classifier mapping features to classes
    # Features X = [
    #   0: is_third_party (0 or 1)
    #   1: domain_entropy (Shannon entropy, typically 1.5 - 5.0)
    #   2: url_length_scaled (len(url) / 100)
    #   3: num_params_scaled (num_params / 5)
    #   4: frequency_scaled (recent_count / 10)
    #   5: keyword_fingerprinting (0 or 1)
    #   6: keyword_ad (0 or 1)
    #   7: keyword_analytics (0 or 1)
    #   8: keyword_tracker (0 or 1)
    # ]
    WEIGHTS = {
        "Fingerprinting": [2.0, 1.5, 0.5, 0.5, 0.5, 12.0, -8.0, -8.0, 0.0],
        "Advertising":    [3.0, 1.0, 1.5, 3.0, 0.5, -8.0, 9.0, -8.0, 0.0],
        "Analytics":      [2.5, 1.0, 0.5, 1.0, 1.0, -8.0, -8.0, 9.0, 0.0],
        "Tracker":        [4.0, 1.5, 1.0, 1.5, 1.5, -8.0, -8.0, -8.0, 9.0],
        "Safe":           [-5.0, 0.0, -1.0, -2.0, -1.0, -10.0, -8.0, -8.0, -8.0]
    }

    BIASES = {
        "Fingerprinting": -3.0,
        "Advertising":    -2.0,
        "Analytics":      -2.0,
        "Tracker":        -1.0,
        "Safe":           4.0
    }

    @staticmethod
    def calculate_entropy(domain: str) -> float:
        """Calculate Shannon Entropy of the domain name string."""
        if not domain:
            return 0.0
        counts = Counter(domain)
        total = len(domain)
        return -sum((count / total) * math.log2(count / total) for count in counts.values())

    @classmethod
    def classify(
        cls,
        domain: str,
        url: str,
        recent_count: int,
        is_third_party: bool
    ) -> str:
        """Classify a request using feature extraction and logit scoring."""
        # Try to run ML prediction first if available
        try:
            from inference.predictor import Predictor
            predictor = Predictor()
            if predictor.model_loaded:
                # Infer request type dynamically from URL or default to other
                inferred_req_type = "other"
                url_lower = url.lower()
                if ".js" in url_lower or "fp.js" in url_lower:
                    inferred_req_type = "script"
                elif any(ext in url_lower for ext in [".png", ".gif", ".jpg", ".jpeg", "/pixel"]):
                    inferred_req_type = "image"
                elif any(term in url_lower for term in ["/collect", "/analytics", "/telemetry"]):
                    inferred_req_type = "xmlhttprequest"

                res = predictor.predict(
                    url=url,
                    request_type=inferred_req_type,
                    third_party=is_third_party,
                    request_frequency=recent_count,
                    referrer_domain=""
                )
                if res:
                    ml_pred = res["prediction"]
                    if ml_pred == "Suspicious":
                        return "Tracker"
                    return ml_pred
        except Exception:
            pass

        domain_lower = domain.lower()
        url_lower = url.lower()

        # 1. Feature Extraction
        is_tp_val = 1.0 if is_third_party else 0.0
        entropy = cls.calculate_entropy(domain_lower)
        url_len_scaled = len(url) / 100.0

        try:
            parsed = urlparse(url_lower)
            num_params = len(parse_qsl(parsed.query))
            url_path_lower = parsed.path
            url_query_lower = parsed.query
        except Exception:
            num_params = 0
            url_path_lower = url_lower
            url_query_lower = ""

        num_params_scaled = num_params / 5.0
        freq_scaled = recent_count / 10.0

        # Helper function for matching keywords with boundary checks for short terms
        def match_keyword(kw: str) -> bool:
            if len(kw) <= 4:
                pattern = r"\b" + re.escape(kw) + r"\b"
                return bool(
                    re.search(pattern, url_path_lower) or
                    re.search(pattern, url_query_lower) or
                    re.search(pattern, domain_lower)
                )
            else:
                return (kw in url_path_lower or kw in url_query_lower or kw in domain_lower)

        # Keyword matching for Fingerprinting
        fp_keywords = ["fingerprint", "fp.js", "canvas", "webgl", "font", "clientjs", "navigator", "user-agent", "mime", "screen"]
        keyword_fp = 1.0 if any(match_keyword(kw) for kw in fp_keywords) else 0.0

        # Keyword matching for Advertising
        ad_keywords = ["ad", "ads", "doubleclick", "banner", "pop", "pixel", "sponsor", "click", "campaign", "marketing", "syndication"]
        keyword_ad = 1.0 if any(match_keyword(kw) for kw in ad_keywords) else 0.0

        # Keyword matching for Analytics
        analytics_keywords = ["analytics", "telemetry", "stats", "metric", "event", "measure", "ga.js"]
        keyword_analytics = 1.0 if any(match_keyword(kw) for kw in analytics_keywords) else 0.0

        # Keyword matching for general Trackers
        tracker_keywords = ["track", "tracker", "tracking", "collect", "log"]
        keyword_tracker = 1.0 if any(match_keyword(kw) for kw in tracker_keywords) else 0.0

        # 2. Vector construction
        X = [
            is_tp_val,
            entropy,
            url_len_scaled,
            num_params_scaled,
            freq_scaled,
            keyword_fp,
            keyword_ad,
            keyword_analytics,
            keyword_tracker
        ]

        # 3. Score calculation
        scores = {}
        for c in cls.CLASSES:
            w = cls.WEIGHTS[c]
            b = cls.BIASES[c]
            score = sum(w_val * x_val for w_val, x_val in zip(w, X)) + b
            scores[c] = score

        # 4. Predict class (Argmax)
        predicted_class = max(scores, key=scores.get)

        # 5. Overrides/Heuristic checks
        if not is_third_party and keyword_fp == 0.0 and keyword_ad == 0.0 and keyword_analytics == 0.0 and keyword_tracker == 0.0:
            return "Safe"

        return predicted_class
