"""Integration Tests — Authentication API.

Tests the full auth flow through the FastAPI TestClient with a real
SQLite database: registration, login, token refresh, profile, 
password management, email verification, and account deletion.
"""

import pytest
from unittest.mock import patch

from backend.tests.conftest import (
    auth_header,
    assert_success,
    assert_error,
    get_json,
    TEST_PASSWORD,
    VALID_PHONE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Registration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistration:
    """Full registration flow tests."""

    @patch("backend.routes.auth.send_verification_email", return_value=True)
    def test_register_valid_user_returns_201(self, mock_email, client, user_register_payload):
        response = client.post("/api/auth/register", json=user_register_payload)
        assert_success(response, 201)
        data = get_json(response)
        assert data["message"] == "Account created successfully. Please check your email to verify your account."
        assert data["user"]["email"] == user_register_payload["email"].lower()
        assert data["user"]["role"] == "citizen"
        assert data["email_sent"] is True

    @patch("backend.routes.auth.send_verification_email", return_value=True)
    def test_register_duplicate_email_returns_409(self, mock_email, client, citizen_user, db):
        response = client.post("/api/auth/register", json={
            "name": "Duplicate User",
            "email": citizen_user.email,
            "password": TEST_PASSWORD,
        })
        assert_error(response, 409)

    @patch("backend.routes.auth.send_verification_email", return_value=True)
    def test_register_weak_password_returns_422(self, mock_email, client):
        response = client.post("/api/auth/register", json={
            "name": "Weak Pass User",
            "email": "weak@test.com",
            "password": "weak",
        })
        # Schema validation or route-level validation should reject
        assert response.status_code in (422,)

    @patch("backend.routes.auth.send_verification_email", return_value=True)
    def test_register_missing_fields_returns_422(self, mock_email, client):
        response = client.post("/api/auth/register", json={})
        assert_error(response, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# Login Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogin:
    """Full login flow tests."""

    def test_login_valid_credentials_returns_tokens(self, client, citizen_user):
        response = client.post("/api/auth/login", json={
            "email": citizen_user.email,
            "password": TEST_PASSWORD,
        })
        assert_success(response, 200)
        data = get_json(response)
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["email"] == citizen_user.email

    def test_login_wrong_password_returns_401(self, client, citizen_user):
        response = client.post("/api/auth/login", json={
            "email": citizen_user.email,
            "password": "WrongP@ss123!",
        })
        assert_error(response, 401)

    def test_login_nonexistent_email_returns_401(self, client):
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": TEST_PASSWORD,
        })
        assert_error(response, 401)

    def test_login_suspended_user_returns_403(self, client, suspended_user):
        response = client.post("/api/auth/login", json={
            "email": suspended_user.email,
            "password": TEST_PASSWORD,
        })
        assert_error(response, 403)

    def test_login_missing_fields_returns_401_or_422(self, client):
        response = client.post("/api/auth/login", json={})
        assert response.status_code in (401, 422)

    def test_login_returns_correct_role(self, client, admin_user):
        response = client.post("/api/auth/login", json={
            "email": admin_user.email,
            "password": TEST_PASSWORD,
        })
        assert_success(response, 200)
        data = get_json(response)
        assert data["user"]["role"] == "admin"


# ═══════════════════════════════════════════════════════════════════════════════
# Token Refresh Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenRefresh:
    """Token refresh flow tests."""

    def test_refresh_with_valid_token(self, client, citizen_user):
        # First login to get refresh token
        login_resp = client.post("/api/auth/login", json={
            "email": citizen_user.email,
            "password": TEST_PASSWORD,
        })
        refresh_token = get_json(login_resp)["refresh_token"]

        # Use refresh token to get new access token
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert_success(response, 200)
        data = get_json(response)
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_with_invalid_token_returns_401(self, client):
        response = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid.token.value",
        })
        assert_error(response, 401)

    def test_refresh_without_token_returns_401(self, client):
        response = client.post("/api/auth/refresh", json={})
        assert_error(response, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# Profile Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfile:
    """Current user profile retrieval tests."""

    def test_get_profile_with_valid_token(self, client, citizen_user, citizen_token):
        response = client.get("/api/auth/me", headers=auth_header(citizen_token))
        assert_success(response, 200)
        data = get_json(response)
        assert data["email"] == citizen_user.email
        assert data["name"] == citizen_user.name
        assert data["role"] == "citizen"

    def test_get_profile_without_token_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert_error(response, 401)

    def test_get_profile_with_invalid_token_returns_401(self, client):
        response = client.get("/api/auth/me", headers=auth_header("invalid.jwt.token"))
        assert_error(response, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# Profile Update Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfileUpdate:
    """Profile update tests."""

    def test_update_name_succeeds(self, client, citizen_token):
        response = client.put(
            "/api/auth/update-profile",
            json={"name": "Updated Name"},
            headers=auth_header(citizen_token),
        )
        assert_success(response, 200)
        data = get_json(response)
        assert data["name"] == "Updated Name"

    def test_update_bio_succeeds(self, client, citizen_token):
        response = client.put(
            "/api/auth/update-profile",
            json={"bio": "I am a test citizen."},
            headers=auth_header(citizen_token),
        )
        assert_success(response, 200)
        assert get_json(response)["bio"] == "I am a test citizen."

    def test_update_without_auth_returns_401(self, client):
        response = client.put("/api/auth/update-profile", json={"name": "Hacker"})
        assert_error(response, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# Password Change Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPasswordChange:
    """Authenticated password change tests."""

    @patch("backend.routes.auth.send_password_changed_email", return_value=True)
    def test_change_password_succeeds(self, mock_email, client, citizen_token):
        response = client.put(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "NewP@ss456!",
                "confirm_password": "NewP@ss456!",
            },
            headers=auth_header(citizen_token),
        )
        assert_success(response, 200)
        assert "successfully" in get_json(response)["message"].lower()

    def test_change_password_wrong_current_returns_400(self, client, citizen_token):
        response = client.put(
            "/api/auth/change-password",
            json={
                "current_password": "WrongP@ss123!",
                "new_password": "NewP@ss456!",
                "confirm_password": "NewP@ss456!",
            },
            headers=auth_header(citizen_token),
        )
        assert_error(response, 400)


# ═══════════════════════════════════════════════════════════════════════════════
# Email Verification Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailVerification:
    """Email verification endpoint tests."""

    def test_verify_valid_token(self, client, unverified_user):
        response = client.get(f"/api/auth/verify-email/test-verification-token-123")
        assert_success(response, 200)
        data = get_json(response)
        assert "verified successfully" in data["message"].lower()

    def test_verify_invalid_token_returns_400(self, client):
        response = client.get("/api/auth/verify-email/invalid-token-xyz")
        assert_error(response, 400)


# ═══════════════════════════════════════════════════════════════════════════════
# Forgot Password Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestForgotPassword:
    """Password reset request tests (anti-enumeration)."""

    @patch("backend.routes.auth.send_password_reset_email", return_value=True)
    def test_forgot_password_existing_email_returns_generic(self, mock_email, client, citizen_user):
        response = client.post("/api/auth/forgot-password", json={
            "email": citizen_user.email,
        })
        assert_success(response, 200)
        data = get_json(response)
        # Must be generic to prevent email enumeration
        assert "if that email" in data["message"].lower()

    def test_forgot_password_nonexistent_email_returns_same_generic(self, client):
        response = client.post("/api/auth/forgot-password", json={
            "email": "nonexistent@test.com",
        })
        assert_success(response, 200)
        data = get_json(response)
        assert "if that email" in data["message"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Logout Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogout:
    """Logout endpoint tests."""

    def test_logout_with_valid_token(self, client, citizen_token):
        response = client.post("/api/auth/logout", headers=auth_header(citizen_token))
        assert_success(response, 200)
        assert "logged out" in get_json(response)["message"].lower()

    def test_logout_without_token_returns_401(self, client):
        response = client.post("/api/auth/logout")
        assert_error(response, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# Account Deletion Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountDeletion:
    """Soft delete and PII anonymization tests."""

    def test_delete_account_with_correct_password(self, client, citizen_token):
        response = client.request(
            "DELETE",
            "/api/auth/delete-account",
            json={"password": TEST_PASSWORD},
            headers=auth_header(citizen_token),
        )
        assert_success(response, 200)
        assert "deleted" in get_json(response)["message"].lower()

    def test_delete_account_wrong_password_returns_400(self, client, citizen_token):
        response = client.request(
            "DELETE",
            "/api/auth/delete-account",
            json={"password": "WrongP@ss123!"},
            headers=auth_header(citizen_token),
        )
        assert_error(response, 400)
