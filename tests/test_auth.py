"""Automated unit tests for authentication endpoints."""

def test_user_registration(client):
    """Test registering a new user."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Citizen",
            "email": "testcitizen@example.com",
            "password": "securepassword123",
            "role": "citizen"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "testcitizen@example.com"
    assert data["full_name"] == "Test Citizen"
    assert "id" in data


def test_user_login(client):
    """Test user login and JWT token issuance."""
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login User",
            "email": "loginuser@example.com",
            "password": "password123",
            "role": "citizen"
        }
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "loginuser@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
