"""Unit Tests — Schema Validation.

Tests Pydantic schema validators for:
- UserRegister: name sanitization, email normalization, password complexity, phone format
- UserLogin: email normalization
- UserChangePassword: password match/differ validation
- IssueCreate: title/description sanitization, coordinate bounds
- IssueStatusUpdate: rejection reason requirement
- CommentCreate: XSS prevention
"""

import pytest
from pydantic import ValidationError

from backend.schemas.user import (
    UserRegister,
    UserLogin,
    UserUpdate,
    UserChangePassword,
    UserForgotPassword,
    UserResetPassword,
    UserRoleUpdate,
)
from backend.schemas.issue import (
    IssueCreate,
    IssueUpdate,
    IssueStatusUpdate,
    IssuePriorityUpdate,
    CommentCreate,
    VoteCreate,
    CitizenResolutionConfirm,
)
from backend.models.user import UserRole
from backend.models.issue import IssueStatus, IssuePriority


# ═══════════════════════════════════════════════════════════════════════════════
# UserRegister Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRegisterSchema:
    """Validate user registration input schema."""

    def test_valid_registration_creates_schema(self):
        data = UserRegister(
            name="Jane Doe",
            email="Jane@Example.COM",
            password="StrongP@ss123!",
            phone="+14155552671",
            role=UserRole.CITIZEN,
        )
        assert data.name == "Jane Doe"
        assert data.email == "jane@example.com"  # Lowercased
        assert data.role == UserRole.CITIZEN

    def test_email_is_lowercased(self):
        data = UserRegister(
            name="Test User",
            email="TEST@UPPER.COM",
            password="StrongP@ss123!",
        )
        assert data.email == "test@upper.com"

    def test_name_too_short_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(name="A", email="a@b.com", password="StrongP@ss123!")
        assert "Name must be between 2 and 100 characters" in str(exc_info.value)

    def test_name_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            UserRegister(name="A" * 101, email="a@b.com", password="StrongP@ss123!")

    def test_name_with_html_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(name="<script>alert(1)</script>", email="a@b.com", password="StrongP@ss123!")
        assert "HTML or script" in str(exc_info.value)

    def test_password_too_short_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(name="Test User", email="a@b.com", password="Short1!")
        assert "at least 8 characters" in str(exc_info.value)

    def test_password_no_uppercase_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(name="Test User", email="a@b.com", password="nouppercase1!")
        assert "uppercase" in str(exc_info.value)

    def test_password_no_lowercase_raises_error(self):
        with pytest.raises(ValidationError):
            UserRegister(name="Test User", email="a@b.com", password="NOLOWERCASE1!")

    def test_password_no_digit_raises_error(self):
        with pytest.raises(ValidationError):
            UserRegister(name="Test User", email="a@b.com", password="NoDigitHere!")

    def test_password_no_special_char_raises_error(self):
        with pytest.raises(ValidationError):
            UserRegister(name="Test User", email="a@b.com", password="NoSpecial123")

    def test_invalid_email_raises_error(self):
        with pytest.raises(ValidationError):
            UserRegister(name="Test User", email="notanemail", password="StrongP@ss123!")

    def test_invalid_phone_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(
                name="Test User",
                email="a@b.com",
                password="StrongP@ss123!",
                phone="abc123",
            )
        assert "phone" in str(exc_info.value).lower()

    def test_valid_phone_accepted(self):
        data = UserRegister(
            name="Test User",
            email="a@b.com",
            password="StrongP@ss123!",
            phone="+14155552671",
        )
        assert data.phone == "+14155552671"

    def test_default_role_is_citizen(self):
        data = UserRegister(
            name="Test User", email="a@b.com", password="StrongP@ss123!"
        )
        assert data.role == UserRole.CITIZEN

    def test_full_name_alias_maps_to_name(self):
        """Test backwards compatibility: full_name → name mapping."""
        data = UserRegister.model_validate({
            "full_name": "Jane Via Alias",
            "email": "jane@alias.com",
            "password": "StrongP@ss123!",
        })
        assert data.name == "Jane Via Alias"


# ═══════════════════════════════════════════════════════════════════════════════
# UserChangePassword Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserChangePasswordSchema:
    """Validate password change schema cross-field validators."""

    def test_valid_password_change(self):
        data = UserChangePassword(
            current_password="OldP@ss123!",
            new_password="NewP@ss456!",
            confirm_password="NewP@ss456!",
        )
        assert data.new_password == "NewP@ss456!"

    def test_passwords_must_match(self):
        with pytest.raises(ValidationError) as exc_info:
            UserChangePassword(
                current_password="OldP@ss123!",
                new_password="NewP@ss456!",
                confirm_password="DifferentP@ss789!",
            )
        assert "do not match" in str(exc_info.value)

    def test_new_password_must_differ_from_current(self):
        with pytest.raises(ValidationError) as exc_info:
            UserChangePassword(
                current_password="SameP@ss123!",
                new_password="SameP@ss123!",
                confirm_password="SameP@ss123!",
            )
        assert "different from current" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# IssueCreate Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueCreateSchema:
    """Validate issue creation input schema."""

    def test_valid_issue_create(self):
        data = IssueCreate(
            title="Pothole on Main Street",
            description="A large pothole causing problems for vehicles and pedestrians.",
            category="infrastructure",
            location_lat=12.9716,
            location_lng=77.5946,
        )
        assert data.title == "Pothole on Main Street"
        assert data.location_lat == 12.9716

    def test_title_too_short_raises_error(self):
        with pytest.raises(ValidationError):
            IssueCreate(
                title="Hi",
                description="A" * 20,
                location_lat=12.0,
                location_lng=77.0,
            )

    def test_description_too_short_raises_error(self):
        with pytest.raises(ValidationError):
            IssueCreate(
                title="Valid Title Here",
                description="Too short",
                location_lat=12.0,
                location_lng=77.0,
            )

    def test_title_with_html_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            IssueCreate(
                title="<script>alert(1)</script>",
                description="A valid description that is long enough.",
                location_lat=12.0,
                location_lng=77.0,
            )
        assert "HTML" in str(exc_info.value)

    def test_description_with_script_raises_error(self):
        with pytest.raises(ValidationError) as exc_info:
            IssueCreate(
                title="Valid Title Here",
                description="Description with <script>evil()</script> in it padding.",
                location_lat=12.0,
                location_lng=77.0,
            )
        assert "script" in str(exc_info.value).lower()

    def test_latitude_out_of_range_raises_error(self):
        with pytest.raises(ValidationError):
            IssueCreate(
                title="Valid Title Here",
                description="A valid description that is definitely long enough.",
                location_lat=91.0,
                location_lng=77.0,
            )

    def test_longitude_out_of_range_raises_error(self):
        with pytest.raises(ValidationError):
            IssueCreate(
                title="Valid Title Here",
                description="A valid description that is definitely long enough.",
                location_lat=12.0,
                location_lng=181.0,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# IssueStatusUpdate Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueStatusUpdateSchema:
    """Validate status update schema with rejection reason requirement."""

    def test_valid_status_update(self):
        data = IssueStatusUpdate(
            status=IssueStatus.ACKNOWLEDGED,
            status_note="Looking into this.",
        )
        assert data.status == IssueStatus.ACKNOWLEDGED

    def test_rejection_requires_reason(self):
        with pytest.raises(ValidationError) as exc_info:
            IssueStatusUpdate(status=IssueStatus.REJECTED)
        assert "rejection reason" in str(exc_info.value).lower()

    def test_rejection_with_reason_succeeds(self):
        data = IssueStatusUpdate(
            status=IssueStatus.REJECTED,
            rejection_reason="Duplicate of existing report #42.",
        )
        assert data.rejection_reason == "Duplicate of existing report #42."


# ═══════════════════════════════════════════════════════════════════════════════
# CommentCreate Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommentCreateSchema:
    """Validate comment creation with XSS prevention."""

    def test_valid_comment(self):
        data = CommentCreate(content="This is a helpful comment.")
        assert data.content == "This is a helpful comment."

    def test_comment_with_script_raises_error(self):
        with pytest.raises(ValidationError):
            CommentCreate(content="Hello <script>evil()</script>")

    def test_comment_too_short_raises_error(self):
        with pytest.raises(ValidationError):
            CommentCreate(content="A")


# ═══════════════════════════════════════════════════════════════════════════════
# UserUpdate Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserUpdateSchema:
    """Validate profile update schema."""

    def test_valid_update(self):
        data = UserUpdate(name="Updated Name", bio="I love my community.")
        assert data.name == "Updated Name"

    def test_bio_with_html_raises_error(self):
        with pytest.raises(ValidationError):
            UserUpdate(bio="Has <script>alert(1)</script>")

    def test_invalid_avatar_url_raises_error(self):
        with pytest.raises(ValidationError):
            UserUpdate(avatar_url="ftp://invalid.com/avatar.jpg")

    def test_valid_avatar_url(self):
        data = UserUpdate(avatar_url="https://example.com/avatar.jpg")
        assert data.avatar_url == "https://example.com/avatar.jpg"

    def test_latitude_out_of_range(self):
        with pytest.raises(ValidationError):
            UserUpdate(location_lat=100.0)
