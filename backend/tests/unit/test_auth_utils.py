"""Unit Tests — Auth Utilities.

Tests password hashing, JWT token creation/verification, and password
strength validation in complete isolation (no database, no network).
"""

import pytest
from datetime import timedelta
from unittest.mock import MagicMock

from backend.utils.auth import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    verify_token,
    generate_verification_token,
    generate_reset_token,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Password Hashing Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPasswordHashing:
    """Verify bcrypt password hashing and verification."""

    def test_hash_password_returns_hash_string(self):
        hashed = hash_password("TestP@ss123!")
        assert isinstance(hashed, str)
        assert hashed != "TestP@ss123!"  # Never stores plaintext

    def test_hash_password_produces_unique_hashes(self):
        """Same password should produce different hashes (salted)."""
        hash1 = hash_password("TestP@ss123!")
        hash2 = hash_password("TestP@ss123!")
        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self):
        hashed = hash_password("TestP@ss123!")
        assert verify_password("TestP@ss123!", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("TestP@ss123!")
        assert verify_password("WrongPassword!", hashed) is False

    def test_verify_password_empty_string(self):
        hashed = hash_password("TestP@ss123!")
        assert verify_password("", hashed) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Password Strength Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPasswordStrength:
    """Validate password strength checker edge cases."""

    def test_strong_password_passes(self):
        result = validate_password_strength("StrongP@ss123!")
        assert result["valid"] is True
        assert len(result.get("errors", [])) == 0

    def test_short_password_fails(self):
        result = validate_password_strength("Ab1!")
        assert result["valid"] is False

    def test_no_uppercase_fails(self):
        result = validate_password_strength("alllowercase1!")
        assert result["valid"] is False

    def test_no_digit_fails(self):
        result = validate_password_strength("NoDigitsHere!")
        assert result["valid"] is False

    def test_no_special_char_fails(self):
        result = validate_password_strength("NoSpecial123")
        assert result["valid"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# JWT Token Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestJWTTokens:
    """Verify JWT token creation and verification."""

    def test_create_access_token_returns_string(self):
        token = create_access_token(
            data={"sub": "1", "uuid": "abc-123", "role": "citizen"},
            expires_delta=timedelta(hours=1),
        )
        assert isinstance(token, str)
        assert len(token) > 20

    def test_verify_valid_access_token(self):
        token = create_access_token(
            data={"sub": "42", "uuid": "uuid-test", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"

    def test_verify_expired_token_returns_none(self):
        token = create_access_token(
            data={"sub": "1", "uuid": "abc", "role": "citizen"},
            expires_delta=timedelta(seconds=-10),  # Already expired
        )
        payload = verify_token(token)
        assert payload is None

    def test_verify_invalid_token_returns_none(self):
        payload = verify_token("not.a.valid.jwt.token")
        assert payload is None

    def test_create_refresh_token_contains_type(self):
        token = create_refresh_token(
            data={"sub": "1", "type": "refresh"},
            expires_delta=timedelta(days=7),
        )
        payload = verify_token(token)
        assert payload is not None
        assert payload.get("type") == "refresh"

    def test_access_and_refresh_tokens_are_different(self):
        access = create_access_token(
            data={"sub": "1", "uuid": "abc", "role": "citizen"},
            expires_delta=timedelta(hours=1),
        )
        refresh = create_refresh_token(
            data={"sub": "1", "type": "refresh"},
            expires_delta=timedelta(days=7),
        )
        assert access != refresh


# ═══════════════════════════════════════════════════════════════════════════════
# Token Generation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenGeneration:
    """Verify verification and reset token generation."""

    def test_verification_token_is_string(self):
        token = generate_verification_token()
        assert isinstance(token, str)
        assert len(token) > 10

    def test_verification_tokens_are_unique(self):
        t1 = generate_verification_token()
        t2 = generate_verification_token()
        assert t1 != t2

    def test_reset_token_is_string(self):
        token = generate_reset_token()
        assert isinstance(token, str)
        assert len(token) > 10

    def test_reset_tokens_are_unique(self):
        t1 = generate_reset_token()
        t2 = generate_reset_token()
        assert t1 != t2
