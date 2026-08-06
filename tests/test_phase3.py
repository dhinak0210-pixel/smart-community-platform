"""Automated unit tests for Phase 3 Volunteer tasks, Notifications, and AI Agent endpoints."""

def test_volunteer_task_flow(client):
    """Test creating, listing, assigning, and completing a volunteer task."""
    # Register authority user
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Municipal Admin",
            "email": "authority@example.com",
            "password": "password123",
            "role": "authority"
        }
    )
    auth_res = client.post(
        "/api/v1/auth/login",
        data={"username": "authority@example.com", "password": "password123"}
    )
    auth_token = auth_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {auth_token}"}

    # Register volunteer user
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Volunteer Joe",
            "email": "volunteer@example.com",
            "password": "password123",
            "role": "volunteer"
        }
    )
    vol_res = client.post(
        "/api/v1/auth/login",
        data={"username": "volunteer@example.com", "password": "password123"}
    )
    vol_token = vol_res.json()["access_token"]
    vol_headers = {"Authorization": f"Bearer {vol_token}"}

    # Create Issue
    issue_payload = {
        "title": "Park Clean Up Needed",
        "description": "Littering after weekend festival near playground",
        "category": "park_maintenance",
        "latitude": 13.08,
        "longitude": 80.27,
        "address": "Central Park"
    }
    create_issue_res = client.post("/api/v1/issues/", json=issue_payload, headers=auth_headers)
    issue_id = create_issue_res.json()["id"]

    # 1. Create Volunteer Task
    task_res = client.post(
        "/api/v1/volunteers/tasks",
        json={"title": "Clean Park Trash", "description": "Help collect bottles", "issue_id": issue_id},
        headers=auth_headers
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    # 2. List Open Tasks
    list_res = client.get("/api/v1/volunteers/tasks?status_filter=open")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Assign Task to Volunteer
    assign_res = client.post(f"/api/v1/volunteers/tasks/{task_id}/assign", headers=vol_headers)
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "assigned"

    # 4. Complete Task
    complete_res = client.post(f"/api/v1/volunteers/tasks/{task_id}/complete", headers=vol_headers)
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "completed"


def test_agent_triage_and_resolution(client):
    """Test AI Agent triage and resolution plan endpoints."""
    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Citizen User",
            "email": "agentuser@example.com",
            "password": "password123",
            "role": "citizen"
        }
    )
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "agentuser@example.com", "password": "password123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Issue
    issue_payload = {
        "title": "Severe Pothole Hazard",
        "description": "Deep crater causing immediate vehicle danger on main road",
        "category": "pothole",
        "latitude": 13.08,
        "longitude": 80.27,
        "address": "Highway 1"
    }
    create_issue_res = client.post("/api/v1/issues/", json=issue_payload, headers=headers)
    issue_id = create_issue_res.json()["id"]

    # Test Triage Endpoint
    triage_res = client.post(f"/api/v1/agents/triage/{issue_id}", headers=headers)
    assert triage_res.status_code == 200
    assert "recommended_priority" in triage_res.json()

    # Test Resolution Plan Endpoint
    plan_res = client.post(f"/api/v1/agents/resolution-plan/{issue_id}", headers=headers)
    assert plan_res.status_code == 200
    assert len(plan_res.json()["resolution_steps"]) >= 4
