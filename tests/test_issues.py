"""Automated unit tests for issue reporting, auto-categorization, and media upload endpoints."""

import io
from PIL import Image


def test_create_and_list_issue(client):
    """Test creating an issue report and retrieving issue list."""
    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Reporter User",
            "email": "reporter@example.com",
            "password": "P@ssword123!",
            "role": "citizen"
        }
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "reporter@example.com", "password": "P@ssword123!"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Issue
    issue_payload = {
        "title": "Broken Street Light on Main St",
        "description": "Street light has been flickering and completely out since yesterday.",
        "category": "utilities",
        "location_lat": 13.0827,
        "location_lng": 80.2707,
        "location_address": "Main Street, Sector 4"
    }
    create_res = client.post("/api/v1/issues/", json=issue_payload, headers=headers)
    assert create_res.status_code == 201
    issue_data = create_res.json()
    assert issue_data["title"] == "Broken Street Light on Main St"

    # List Issues
    list_res = client.get("/api/v1/issues/")
    assert list_res.status_code == 200
    res_data = list_res.json()
    issues = res_data["issues"] if "issues" in res_data else res_data
    assert len(issues) >= 1
    assert issues[0]["uuid"] == issue_data["uuid"] or issues[0]["title"] == issue_data["title"]


def test_auto_categorization(client):
    """Test auto-categorization endpoint for text descriptions."""
    res = client.post(
        "/api/v1/issues/auto-categorize",
        json={"title": "Deep Pothole", "description": "Large crater in the middle of asphalt road"}
    )
    assert res.status_code == 200
    assert res.json()["predicted_category"] == "infrastructure"


def test_image_upload(client):
    """Test image upload endpoint with valid PIL generated image."""
    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Uploader User",
            "email": "uploader@example.com",
            "password": "P@ssword123!",
            "role": "citizen"
        }
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "uploader@example.com", "password": "P@ssword123!"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Generate small test PNG image in memory
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    upload_res = client.post(
        "/api/v1/issues/upload",
        files={"file": ("test.png", img_bytes, "image/png")},
        headers=headers
    )
    assert upload_res.status_code == 200
    assert "image_url" in upload_res.json()
