#!/usr/bin/env python3
"""
Comprehensive Health Verification Suite for Free Tier Deployment.
Usage: python scripts/health_check_free.py [URL]
Example: python scripts/health_check_free.py https://smart-community-api.onrender.com
"""

import sys
import time
from datetime import datetime

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TIMEOUT = 60  # Allow 60s max for potential free tier cold start

CHECKS = []


def check(name: str, critical: bool = True):
    def decorator(func):
        CHECKS.append((name, func, critical))
        return func
    return decorator


@check("Root API reachable", critical=True)
def check_api():
    r = httpx.get(f"{BASE_URL}/", timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return r.json()


@check("Health Check endpoint", critical=True)
def check_health():
    r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data.get("status") == "healthy", f"Status is {data.get('status')}"
    return data


@check("Database connected", critical=True)
def check_db():
    r = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    data = r.json()
    db_info = data.get("checks", {}).get("database", "")
    assert "connected" in str(db_info).lower(), f"DB check failed: {db_info}"
    return {"database": db_info}


@check("Issues List API endpoint", critical=True)
def check_issues():
    r = httpx.get(f"{BASE_URL}/api/issues/", timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "issues" in data, "No 'issues' key in response"
    return {"total_issues": data.get("total", len(data.get("issues", [])))}


@check("Map Markers API endpoint", critical=True)
def check_map():
    r = httpx.get(f"{BASE_URL}/api/issues/map", timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "markers" in data, "No 'markers' key in response"
    return {"markers_count": data.get("total", len(data.get("markers", [])))}


@check("Auth security rejection check", critical=True)
def check_auth():
    r = httpx.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "nonexistent@test.com", "password": "InvalidPassword123!"},
        timeout=TIMEOUT
    )
    assert r.status_code == 401, f"Expected 401 Unauthorized, got {r.status_code}"
    return {"auth_verification": "Correctly rejected bad credentials"}


@check("Analytics Stats endpoint", critical=True)
def check_stats():
    r = httpx.get(f"{BASE_URL}/api/issues/stats", timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "total_issues" in data or "total" in data, "Stats missing issue count"
    return data


@check("AI Text Classification Endpoint", critical=False)
def check_ai_classify():
    r = httpx.post(
        f"{BASE_URL}/api/ai/classify-text",
        json={"title": "pothole on main street", "description": "dangerous deep pothole in asphalt"},
        timeout=TIMEOUT
    )
    assert r.status_code in [200, 401, 422], f"Unexpected status: {r.status_code}"
    return {"ai_status_code": r.status_code}


@check("Swagger OpenAPI Docs", critical=False)
def check_docs():
    r = httpx.get(f"{BASE_URL}/docs", timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return {"docs": "Swagger UI accessible"}


def run():
    print(f"\n{'═'*65}")
    print(f"  Smart Community Platform - Free Tier Health Verification")
    print(f"  Target URL: {BASE_URL}")
    print(f"  Timestamp:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Note:       First request may take 30-50s if waking from cold start")
    print(f"{'═'*65}\n")

    passed = 0
    failed = 0
    warnings = 0

    for name, func, critical in CHECKS:
        start_t = time.time()
        try:
            res = func()
            elapsed_ms = round((time.time() - start_t) * 1000)
            passed += 1
            print(f"  ✅ {name} ({elapsed_ms}ms)")
            if res and isinstance(res, dict):
                for k, v in list(res.items())[:2]:
                    print(f"     └─ {k}: {str(v)[:65]}")
        except Exception as e:
            elapsed_ms = round((time.time() - start_t) * 1000)
            if critical:
                failed += 1
                print(f"  ❌ {name} ({elapsed_ms}ms)")
                print(f"     └─ Error: {str(e)[:80]}")
            else:
                warnings += 1
                print(f"  ⚠️  {name} ({elapsed_ms}ms) - non-critical")
                print(f"     └─ Info: {str(e)[:80]}")

    print(f"\n{'─'*65}")
    print(f"  Results: {passed} passed | {failed} failed | {warnings} warnings")
    print(f"{'─'*65}")

    if failed == 0:
        print(f"\n  🎉 ALL CRITICAL CHECKS PASSED SUCCESSFULLY!")
        print(f"  Your platform is active, responsive, and ready for public traffic.\n")
        sys.exit(0)
    else:
        print(f"\n  💥 {failed} CRITICAL CHECK(S) FAILED!")
        print(f"  Review application logs before sharing with users.\n")
        sys.exit(1)


if __name__ == "__main__":
    run()
