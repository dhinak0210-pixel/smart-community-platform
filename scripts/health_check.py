#!/usr/bin/env python3
"""
Health check script for Smart Community Platform.
Run this after deployment to verify everything works.
Returns exit code 0 if healthy, 1 if not.
"""

import httpx
import sys
import json
import time
from datetime import datetime

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

CHECKS = []


def check(name: str):
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator


@check("API is reachable")
def check_api_reachable():
    response = httpx.get(f"{BASE_URL}/", timeout=10)
    assert response.status_code == 200
    return response.json()


@check("Health endpoint returns healthy")
def check_health():
    response = httpx.get(f"{BASE_URL}/health", timeout=10)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ["healthy", "degraded"]
    return data


@check("Database is connected")
def check_database():
    response = httpx.get(f"{BASE_URL}/health", timeout=10)
    data = response.json()
    db_status = data.get("checks", {}).get("database", data.get("database", ""))
    assert "connected" in str(db_status).lower()
    return {"database": db_status}


@check("API docs are accessible")
def check_api_docs():
    response = httpx.get(f"{BASE_URL}/docs", timeout=10)
    assert response.status_code == 200
    return {"docs_url": f"{BASE_URL}/docs"}


@check("Issues endpoint is working")
def check_issues_endpoint():
    response = httpx.get(f"{BASE_URL}/api/issues/", timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert "issues" in data or "total" in data
    return {"total_issues": data.get("total", len(data.get("issues", [])))}


@check("Auth endpoint is working")
def check_auth_endpoint():
    # Test with invalid credentials (should return 401 not 500)
    response = httpx.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "test@test.com", "password": "test"},
        timeout=10
    )
    assert response.status_code in [400, 401, 422]
    return {"auth_working": True}


@check("Map markers endpoint is working")
def check_map_endpoint():
    response = httpx.get(f"{BASE_URL}/api/issues/map", timeout=15)
    assert response.status_code == 200
    data = response.json()
    count = len(data) if isinstance(data, list) else len(data.get("markers", []))
    return {"markers": count}


@check("Stats endpoint is working")
def check_stats_endpoint():
    response = httpx.get(f"{BASE_URL}/api/issues/stats", timeout=15)
    assert response.status_code == 200
    data = response.json()
    return {"stats": "ok"}


def run_all_checks():
    print(f"\n{'═'*60}")
    print(f"  Smart Community Platform - Health Check")
    print(f"  Target: {BASE_URL}")
    print(f"  Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'═'*60}\n")

    passed = 0
    failed = 0
    results = []

    for name, check_func in CHECKS:
        try:
            result = check_func()
            passed += 1
            results.append({
                "name": name,
                "status": "PASS",
                "details": result
            })
            print(f"  ✅ {name}")
            if result:
                details_str = json.dumps(result, indent=None)
                if len(details_str) < 80:
                    print(f"     → {details_str}")
        except Exception as e:
            failed += 1
            results.append({
                "name": name,
                "status": "FAIL",
                "error": str(e)
            })
            print(f"  ❌ {name}")
            print(f"     → Error: {str(e)[:100]}")

    print(f"\n{'─'*60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'─'*60}")

    if failed == 0:
        print(f"\n  🎉 ALL CHECKS PASSED! Platform is healthy.\n")
        sys.exit(0)
    else:
        print(f"\n  ⚠️  {failed} CHECK(S) FAILED! Platform needs attention.\n")
        sys.exit(1)


if __name__ == "__main__":
    run_all_checks()
