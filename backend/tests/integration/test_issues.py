"""Integration Tests — Issues API.

Tests the full issue lifecycle through the FastAPI TestClient:
- CRUD operations (create, read, update, list)
- Status transitions (authority/admin only)
- Priority overrides
- Voting (toggle on/off)
- Comments (add, delete)
- RBAC enforcement (citizen vs authority vs admin)
- Search, filtering, and pagination
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.tests.conftest import (
    auth_header,
    assert_success,
    assert_error,
    get_json,
    TEST_PASSWORD,
)
from backend.models.issue import IssueStatus, IssuePriority, IssueCategory


# ═══════════════════════════════════════════════════════════════════════════════
# Issue Creation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueCreation:
    """Test issue creation endpoint with AI auto-triage."""

    @patch("backend.routes.issues.run_pipeline_background")
    @patch("backend.routes.issues.categorize_text")
    @patch("backend.routes.issues.generate_issue_tags", return_value=["pothole", "road"])
    def test_create_issue_returns_201(
        self, mock_tags, mock_categorize, mock_pipeline,
        client, citizen_token, issue_create_payload
    ):
        mock_categorize.return_value = IssueCategory.WASTE
        response = client.post(
            "/api/issues/",
            json=issue_create_payload,
            headers=auth_header(citizen_token),
        )
        assert_success(response, 201)
        data = get_json(response)
        assert data["title"] == issue_create_payload["title"]
        assert data["status"] == "reported"
        assert data["uuid"] is not None

    def test_create_issue_without_auth_returns_401(self, client, issue_create_payload):
        response = client.post("/api/issues/", json=issue_create_payload)
        assert_error(response, 401)

    @patch("backend.routes.issues.run_pipeline_background")
    @patch("backend.routes.issues.categorize_text")
    @patch("backend.routes.issues.generate_issue_tags", return_value=[])
    def test_create_issue_missing_required_fields_returns_422(
        self, mock_tags, mock_categorize, mock_pipeline, client, citizen_token
    ):
        mock_categorize.return_value = IssueCategory.OTHER
        response = client.post(
            "/api/issues/",
            json={"title": "Hi"},  # Missing description, coordinates
            headers=auth_header(citizen_token),
        )
        assert_error(response, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# Issue Retrieval Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueRetrieval:
    """Test issue detail retrieval and view count increment."""

    def test_get_issue_by_uuid(self, client, sample_issue):
        response = client.get(f"/api/issues/{sample_issue.uuid}")
        assert_success(response, 200)
        data = get_json(response)
        assert data["title"] == sample_issue.title
        assert data["uuid"] == str(sample_issue.uuid)

    def test_get_issue_increments_view_count(self, client, sample_issue):
        initial_views = sample_issue.view_count or 0
        client.get(f"/api/issues/{sample_issue.uuid}")
        response = client.get(f"/api/issues/{sample_issue.uuid}")
        data = get_json(response)
        assert data["view_count"] >= initial_views + 1

    def test_get_nonexistent_issue_returns_404(self, client):
        import uuid
        fake_uuid = uuid.uuid4()
        response = client.get(f"/api/issues/{fake_uuid}")
        assert_error(response, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# Issue Listing Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueListing:
    """Test paginated issue listing with filters."""

    def test_list_issues_returns_paginated_response(self, client, sample_issue):
        response = client.get("/api/issues/")
        assert_success(response, 200)
        data = get_json(response)
        assert "issues" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert data["total"] >= 1

    def test_list_issues_with_category_filter(self, client, sample_issue):
        response = client.get("/api/issues/?category=infrastructure")
        assert_success(response, 200)
        data = get_json(response)
        for issue in data["issues"]:
            assert issue["category"] == "infrastructure"

    def test_list_issues_with_search(self, client, sample_issue):
        response = client.get("/api/issues/?search=pothole")
        assert_success(response, 200)
        data = get_json(response)
        assert data["total"] >= 1

    def test_list_issues_pagination(self, client, sample_issue):
        response = client.get("/api/issues/?page=1&page_size=5")
        assert_success(response, 200)
        data = get_json(response)
        assert data["page"] == 1
        assert data["page_size"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Issue Update Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueUpdate:
    """Test issue detail updates by reporter and admin."""

    def test_reporter_can_update_own_issue(self, client, sample_issue, citizen_token):
        response = client.put(
            f"/api/issues/{sample_issue.uuid}",
            json={"title": "Updated pothole report with more details"},
            headers=auth_header(citizen_token),
        )
        assert_success(response, 200)
        data = get_json(response)
        assert data["title"] == "Updated pothole report with more details"

    def test_admin_can_update_any_issue(self, client, sample_issue, admin_token):
        response = client.put(
            f"/api/issues/{sample_issue.uuid}",
            json={"title": "Admin corrected the issue title here"},
            headers=auth_header(admin_token),
        )
        assert_success(response, 200)

    def test_other_user_cannot_update_issue(self, client, sample_issue, authority_token):
        response = client.put(
            f"/api/issues/{sample_issue.uuid}",
            json={"title": "Unauthorized change attempt here"},
            headers=auth_header(authority_token),
        )
        assert_error(response, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# Status Transition Tests (RBAC)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusTransitions:
    """Test status updates with role-based access control."""

    @patch("backend.routes.issues.send_issue_status_update_email", return_value=True)
    def test_authority_can_change_status(self, mock_email, client, sample_issue, authority_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/status",
            json={"status": "acknowledged", "status_note": "We are looking into this."},
            headers=auth_header(authority_token),
        )
        assert_success(response, 200)
        data = get_json(response)
        assert data["status"] == "acknowledged"

    def test_citizen_cannot_change_status(self, client, sample_issue, citizen_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/status",
            json={"status": "acknowledged"},
            headers=auth_header(citizen_token),
        )
        assert_error(response, 403)

    @patch("backend.routes.issues.send_issue_status_update_email", return_value=True)
    def test_admin_can_change_status(self, mock_email, client, sample_issue, admin_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/status",
            json={"status": "in_progress", "status_note": "Team deployed."},
            headers=auth_header(admin_token),
        )
        assert_success(response, 200)

    @patch("backend.routes.issues.send_issue_status_update_email", return_value=True)
    def test_rejection_requires_reason(self, mock_email, client, sample_issue, authority_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/status",
            json={"status": "rejected"},
            headers=auth_header(authority_token),
        )
        assert_error(response, 422)

    @patch("backend.routes.issues.send_issue_status_update_email", return_value=True)
    def test_rejection_with_reason_succeeds(self, mock_email, client, sample_issue, authority_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/status",
            json={
                "status": "rejected",
                "rejection_reason": "This is a duplicate of issue #42.",
            },
            headers=auth_header(authority_token),
        )
        assert_success(response, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority Override Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPriorityOverride:
    """Test priority updates with RBAC."""

    def test_authority_can_change_priority(self, client, sample_issue, authority_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/priority",
            json={"priority": "critical", "reason": "Safety hazard detected."},
            headers=auth_header(authority_token),
        )
        assert_success(response, 200)
        data = get_json(response)
        assert data["priority"] == "critical"

    def test_citizen_cannot_change_priority(self, client, sample_issue, citizen_token):
        response = client.patch(
            f"/api/issues/{sample_issue.uuid}/priority",
            json={"priority": "critical"},
            headers=auth_header(citizen_token),
        )
        assert_error(response, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# Voting Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoting:
    """Test issue upvote toggle behavior."""

    def test_vote_on_issue(self, client, sample_issue, citizen_token):
        response = client.post(
            f"/api/issues/{sample_issue.uuid}/vote",
            json={},
            headers=auth_header(citizen_token),
        )
        # First vote creates it → 200 or 201
        assert response.status_code in (200, 201)

    def test_vote_nonexistent_issue_returns_404(self, client, citizen_token):
        import uuid
        fake_uuid = uuid.uuid4()
        response = client.post(
            f"/api/issues/{fake_uuid}/vote",
            json={},
            headers=auth_header(citizen_token),
        )
        assert_error(response, 404)

    def test_vote_without_auth_returns_401(self, client, sample_issue):
        response = client.post(f"/api/issues/{sample_issue.uuid}/vote", json={})
        assert_error(response, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# Comment Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestComments:
    """Test issue comment CRUD."""

    def test_add_comment_to_issue(self, client, sample_issue, citizen_token):
        response = client.post(
            f"/api/issues/{sample_issue.uuid}/comments",
            json={"content": "This is a test comment on the issue."},
            headers=auth_header(citizen_token),
        )
        assert_success(response, 201)
        data = get_json(response)
        assert data["content"] == "This is a test comment on the issue."

    def test_comment_without_auth_returns_401(self, client, sample_issue):
        response = client.post(
            f"/api/issues/{sample_issue.uuid}/comments",
            json={"content": "Unauthorized comment"},
        )
        assert_error(response, 401)

    def test_comment_on_nonexistent_issue_returns_404(self, client, citizen_token):
        import uuid
        fake_uuid = uuid.uuid4()
        response = client.post(
            f"/api/issues/{fake_uuid}/comments",
            json={"content": "Comment on nothing here."},
            headers=auth_header(citizen_token),
        )
        assert_error(response, 404)

    def test_delete_own_comment(self, client, sample_issue, sample_comment, citizen_token):
        response = client.delete(
            f"/api/issues/{sample_issue.uuid}/comments/{sample_comment.uuid}",
            headers=auth_header(citizen_token),
        )
        assert_success(response, 200)

    def test_authority_comment_type_auto_assigned(self, client, sample_issue, authority_token):
        response = client.post(
            f"/api/issues/{sample_issue.uuid}/comments",
            json={"content": "Official authority response to this issue."},
            headers=auth_header(authority_token),
        )
        assert_success(response, 201)
        data = get_json(response)
        assert data["comment_type"] == "authority_update"


# ═══════════════════════════════════════════════════════════════════════════════
# Map Markers Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapMarkers:
    """Test map marker endpoint."""

    def test_get_map_markers(self, client, sample_issue):
        response = client.get("/api/issues/map")
        assert_success(response, 200)
        data = get_json(response)
        assert isinstance(data, list)
        assert len(data) >= 1
        marker = data[0]
        assert "uuid" in marker
        assert "location_lat" in marker
        assert "location_lng" in marker

    def test_map_markers_with_category_filter(self, client, sample_issue):
        response = client.get("/api/issues/map?category=infrastructure")
        assert_success(response, 200)
