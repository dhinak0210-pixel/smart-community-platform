"""End-to-End Tests — Full User Journeys.

Tests complete multi-step user flows that simulate real citizen, 
authority, and admin workflows from registration to issue resolution.
"""

import pytest
from unittest.mock import patch

from backend.tests.conftest import (
    auth_header,
    assert_success,
    assert_error,
    get_json,
    TEST_PASSWORD,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Citizen Journey: Register → Login → Report → Comment → Vote
# ═══════════════════════════════════════════════════════════════════════════════

class TestCitizenJourney:
    """Complete citizen user journey from registration to community engagement."""

    @patch("backend.routes.auth.send_verification_email", return_value=True)
    @patch("backend.routes.issues.run_pipeline_background")
    @patch("backend.routes.issues.categorize_text")
    @patch("backend.routes.issues.generate_issue_tags", return_value=["pothole"])
    def test_citizen_full_lifecycle(
        self, mock_tags, mock_categorize, mock_pipeline, mock_email,
        client, db
    ):
        """Citizen registers → logs in → reports issue → comments → votes."""
        from backend.models.issue import IssueCategory
        mock_categorize.return_value = IssueCategory.INFRASTRUCTURE

        # Step 1: Register
        reg_payload = {
            "name": "Journey Citizen",
            "email": "journey_citizen@test.com",
            "password": TEST_PASSWORD,
            "role": "citizen",
        }
        reg_resp = client.post("/api/auth/register", json=reg_payload)
        assert_success(reg_resp, 201)

        # Step 2: Login
        login_resp = client.post("/api/auth/login", json={
            "email": "journey_citizen@test.com",
            "password": TEST_PASSWORD,
        })
        assert_success(login_resp, 200)
        tokens = get_json(login_resp)
        access_token = tokens["access_token"]
        headers = auth_header(access_token)

        # Step 3: Check Profile
        profile_resp = client.get("/api/auth/me", headers=headers)
        assert_success(profile_resp, 200)
        profile = get_json(profile_resp)
        assert profile["name"] == "Journey Citizen"

        # Step 4: Report Issue
        issue_payload = {
            "title": "Journey test pothole on Main Street",
            "description": "A large pothole on Main Street that needs urgent repair for safety.",
            "category": "infrastructure",
            "location_lat": 12.9716,
            "location_lng": 77.5946,
            "location_city": "TestCity",
        }
        issue_resp = client.post("/api/issues/", json=issue_payload, headers=headers)
        assert_success(issue_resp, 201)
        issue_data = get_json(issue_resp)
        issue_uuid = issue_data["uuid"]
        assert issue_data["status"] == "reported"

        # Step 5: View the issue
        view_resp = client.get(f"/api/issues/{issue_uuid}")
        assert_success(view_resp, 200)
        assert get_json(view_resp)["view_count"] >= 1

        # Step 6: Add comment
        comment_resp = client.post(
            f"/api/issues/{issue_uuid}/comments",
            json={"content": "I drive past this every day. Very dangerous!"},
            headers=headers,
        )
        assert_success(comment_resp, 201)

        # Step 7: Vote on issue
        vote_resp = client.post(
            f"/api/issues/{issue_uuid}/vote",
            json={},
            headers=headers,
        )
        assert vote_resp.status_code in (200, 201)

        # Step 8: Update profile
        update_resp = client.put(
            "/api/auth/update-profile",
            json={"bio": "Active community member."},
            headers=headers,
        )
        assert_success(update_resp, 200)

        # Step 9: Logout
        logout_resp = client.post("/api/auth/logout", headers=headers)
        assert_success(logout_resp, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# Authority Journey: Login → Review Issues → Change Status → Resolve
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthorityJourney:
    """Authority reviews, triages, and resolves reported issues."""

    @patch("backend.routes.issues.send_issue_status_update_email", return_value=True)
    def test_authority_triage_and_resolve(
        self, mock_email, client, authority_token, sample_issue
    ):
        """Authority acknowledges → assigns → marks in_progress → resolves."""
        headers = auth_header(authority_token)
        issue_uuid = str(sample_issue.uuid)

        # Step 1: List all issues
        list_resp = client.get("/api/issues/", headers=headers)
        assert_success(list_resp, 200)
        assert get_json(list_resp)["total"] >= 1

        # Step 2: View issue detail
        detail_resp = client.get(f"/api/issues/{issue_uuid}", headers=headers)
        assert_success(detail_resp, 200)

        # Step 3: Acknowledge
        ack_resp = client.patch(
            f"/api/issues/{issue_uuid}/status",
            json={"status": "acknowledged", "status_note": "Received and reviewing."},
            headers=headers,
        )
        assert_success(ack_resp, 200)
        assert get_json(ack_resp)["status"] == "acknowledged"

        # Step 4: Set in_progress
        progress_resp = client.patch(
            f"/api/issues/{issue_uuid}/status",
            json={"status": "in_progress", "status_note": "Repair team deployed."},
            headers=headers,
        )
        assert_success(progress_resp, 200)
        assert get_json(progress_resp)["status"] == "in_progress"

        # Step 5: Set priority to high
        priority_resp = client.patch(
            f"/api/issues/{issue_uuid}/priority",
            json={"priority": "high", "reason": "Multiple citizen reports."},
            headers=headers,
        )
        assert_success(priority_resp, 200)

        # Step 6: Add authority comment
        comment_resp = client.post(
            f"/api/issues/{issue_uuid}/comments",
            json={"content": "Our team is working on this. ETA: 2 days."},
            headers=headers,
        )
        assert_success(comment_resp, 201)

        # Step 7: Submit resolution
        resolve_resp = client.patch(
            f"/api/issues/{issue_uuid}/resolution",
            json={
                "resolution_note": "Pothole has been filled with asphalt and road is safe for use.",
                "resolved_by_department": "Department of Public Works",
            },
            headers=headers,
        )
        assert_success(resolve_resp, 200)
        assert get_json(resolve_resp)["status"] == "resolved"


# ═══════════════════════════════════════════════════════════════════════════════
# Admin Journey: Login → Manage Users → Override Issues → View Stats
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdminJourney:
    """Admin manages the platform: views stats, overrides issues."""

    @patch("backend.routes.issues.send_issue_status_update_email", return_value=True)
    def test_admin_platform_management(
        self, mock_email, client, admin_token, sample_issue
    ):
        """Admin views stats → updates any issue → changes status."""
        headers = auth_header(admin_token)
        issue_uuid = str(sample_issue.uuid)

        # Step 1: View profile
        profile_resp = client.get("/api/auth/me", headers=headers)
        assert_success(profile_resp, 200)
        assert get_json(profile_resp)["role"] == "admin"

        # Step 2: List all issues
        list_resp = client.get("/api/issues/", headers=headers)
        assert_success(list_resp, 200)

        # Step 3: Update any issue (admin privilege)
        update_resp = client.put(
            f"/api/issues/{issue_uuid}",
            json={"title": "Admin-corrected: Large pothole requiring urgent attention"},
            headers=headers,
        )
        assert_success(update_resp, 200)

        # Step 4: Override status directly
        status_resp = client.patch(
            f"/api/issues/{issue_uuid}/status",
            json={"status": "assigned", "status_note": "Assigned to engineering team."},
            headers=headers,
        )
        assert_success(status_resp, 200)

        # Step 5: Override priority
        priority_resp = client.patch(
            f"/api/issues/{issue_uuid}/priority",
            json={"priority": "critical", "reason": "Admin escalation: safety concern."},
            headers=headers,
        )
        assert_success(priority_resp, 200)
        assert get_json(priority_resp)["priority"] == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check Journey
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthCheckJourney:
    """Test platform health endpoints."""

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert_success(response, 200)
        data = get_json(response)
        assert "app" in data
        assert "version" in data

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert_success(response, 200)
        data = get_json(response)
        assert "status" in data

    def test_api_discovery_endpoint(self, client):
        response = client.get("/api")
        assert_success(response, 200)
        data = get_json(response)
        assert "total" in data
        assert "endpoints" in data
        assert data["total"] > 0
