import sys
import os
import re

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.classifier import TrackerClassifier

def run_tests():
    test_cases = [
        # (domain, url, recent_count, is_third_party, expected_class)
        (
            "google-analytics.com",
            "https://www.google-analytics.com/g/collect?v=2&tid=UA-1234&cid=555",
            1,
            True,
            "Analytics"
        ),
        (
            "doubleclick.net",
            "https://ad.doubleclick.net/ddm/adj/N1234.5678;sz=300x250;ord=9876",
            2,
            True,
            "Advertising"
        ),
        (
            "fingerprinting.evil.com",
            "https://fingerprinting.evil.com/fp.js?canvas=1&webgl=1",
            1,
            True,
            "Fingerprinting"
        ),
        (
            "random-domain-abcdefgh.com",
            "https://random-domain-abcdefgh.com/track?uid=123",
            12,  # high frequency
            True,
            "Tracker"
        ),
        (
            "localhost",
            "http://localhost/static/logo.png",
            0,
            False,
            "Safe"
        ),
        (
            "mycorp.com",
            "https://mycorp.com/api/userdata",
            1,
            False,
            "Safe"
        )
    ]

    passed = True
    print("Running TrackerClassifier Verification Tests...")
    for idx, (domain, url, freq, is_tp, expected) in enumerate(test_cases):
        pred = TrackerClassifier.classify(domain, url, freq, is_tp)
        if pred == expected:
            print(f"[{idx+1}] PASS: {domain} -> {pred}")
        else:
            print(f"[{idx+1}] FAIL: {domain} -> {pred} (expected {expected})")
            passed = False
            
    if passed:
        print("\nAll tests PASSED successfully!")
    else:
        print("\nSome tests FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
