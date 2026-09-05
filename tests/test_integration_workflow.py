"""
Integration test for the complete submission workflow:
CREATE INTERNSHIP
→ START TASK
→ SUBMIT FILE
→ AI REVIEW
→ CHANGES REQUIRED
→ RESUBMIT
→ AI REVIEW
→ MANAGER APPROVAL
→ TASK COMPLETED
"""
import io
import json
from jose import jwt

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


client = TestClient(app)


def make_token(student_id: str = "student_001") -> str:
    return jwt.encode(
        {"sub": student_id, "student_id": student_id, "role": "student"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def test_complete_submission_workflow():
    """Full integration test: internship generation → task start → submit → AI review → changes → resubmit → AI review → manager approval → completed."""
    headers = {"Authorization": f"Bearer {make_token('student_integration')}"}
    
    # 1. CREATE INTERNSHIP - Generate company, project, sprints, tasks
    resp = client.post(
        "/api/generate",
        headers=headers,
        json={
            "student_id": "student_integration",
            "role": "Backend Developer",
            "technology_stack": ["Python", "FastAPI", "PostgreSQL"],
            "difficulty": "intermediate",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 201, f"Generate failed: {resp.text}"
    data = resp.json()
    company_id = data["company_id"]
    project_id = data["project_id"]
    sprint_ids = data["sprint_ids"]
    task_count = data["task_count"]
    assert task_count > 0
    assert len(sprint_ids) == 4
    
    # 2. Get a task without dependencies to start
    board = client.get(f"/api/projects/{project_id}/board", headers=headers).json()
    task_id = None
    for status_list in board.values():
        for task in status_list:
            if not task["depends_on_task_ids"]:
                task_id = task["id"]
                break
        if task_id:
            break
    assert task_id is not None, "No task without dependencies found"
    
    # 3. START TASK - Move from BACKLOG to IN_PROGRESS
    resp = client.post(
        f"/api/projects/{project_id}/submissions/tasks/{task_id}/start",
        headers=headers,
    )
    assert resp.status_code == 200, f"Start task failed: {resp.text}"
    start_result = resp.json()
    assert start_result["status"] == "started"
    assert start_result["task_status"] == "in_progress"
    
    # 4. SUBMIT FILE - Submit work for the task
    file_content = b"def hello():\n    return 'Hello World'\n"
    files = {"files": ("main.py", io.BytesIO(file_content), "text/x-python")}
    resp = client.post(
        f"/api/projects/{project_id}/submissions/tasks/{task_id}/submit",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 201, f"Submit failed: {resp.text}"
    submit_result = resp.json()
    assert "submission_id" in submit_result
    assert "version_id" in submit_result
    assert submit_result["status"] == "submitted"
    submission_id = submit_result["submission_id"]
    version_id = submit_result["version_id"]
    
    # 5. AI REVIEW - Trigger AI review of the submission
    resp = client.post(
        f"/api/projects/{project_id}/reviews/versions/{version_id}",
        headers=headers,
    )
    assert resp.status_code == 201, f"AI review failed: {resp.text}"
    ai_review = resp.json()
    assert "review_id" in ai_review
    assert ai_review["result"] in ["approved", "changes_required", "rejected"]
    
    # If AI approves, skip to manager approval. If changes required, test the full flow.
    if ai_review["result"] == "approved":
        # 6. MANAGER APPROVAL - Manager reviews and approves
        resp = client.post(
            f"/api/projects/{project_id}/reviews/versions/{version_id}/manager-review",
            headers=headers,
        )
        assert resp.status_code == 201, f"Manager review failed: {resp.text}"
        manager_review = resp.json()
        assert manager_review["manager_result"] in ["approved", "changes_required"]
        
        if manager_review["manager_result"] == "approved":
            # 7. Task should be COMPLETED
            assert manager_review["final_task_status"] == "completed"
        else:
            # Changes required - would need to resubmit
            pytest.skip("Manager requested changes, but AI approved")
    else:
        # 6. CHANGES REQUESTED - AI requested changes
        assert ai_review["result"] == "changes_required"
        
        # 7. RESUBMIT - Fix issues and resubmit
        file_content_v2 = b"def hello():\n    return 'Hello World!'\n"
        files = {"files": ("main.py", io.BytesIO(file_content_v2), "text/x-python")}
        resp = client.post(
            f"/api/projects/{project_id}/submissions/versions/{version_id}/resubmit",
            headers=headers,
            files=files,
        )
        assert resp.status_code == 201, f"Resubmit failed: {resp.text}"
        resubmit_result = resp.json()
        assert resubmit_result["version"] == 2
        new_version_id = resubmit_result["version_id"]
        
        # 8. AI REVIEW AGAIN
        resp = client.post(
            f"/api/projects/{project_id}/reviews/versions/{new_version_id}",
            headers=headers,
        )
        assert resp.status_code == 201, f"Second AI review failed: {resp.text}"
        ai_review2 = resp.json()
        assert ai_review2["result"] in ["approved", "changes_required", "rejected"]
        
        if ai_review2["result"] == "approved":
            # 9. MANAGER APPROVAL
            resp = client.post(
                f"/api/projects/{project_id}/reviews/versions/{new_version_id}/manager-review",
                headers=headers,
            )
            assert resp.status_code == 201, f"Second manager review failed: {resp.text}"
            manager_review = resp.json()
            assert manager_review["manager_result"] in ["approved", "changes_required"]
            
            if manager_review["manager_result"] == "approved":
                assert manager_review["final_task_status"] == "completed"
    
    # Verify task is completed
    task = client.get(f"/api/tasks/{task_id}", headers=headers).json()
    assert task["status"] == "completed", f"Task not completed: {task['status']}"
    
    # Verify all events were created
    events = client.get(f"/api/projects/{project_id}/events", headers=headers).json()
    event_types = {e["event_type"] for e in events}
    required_events = {"task_started", "submission_created", "submission_version_created", 
                       "review_started", "ai_review_completed", "manager_approved", "task_completed"}
    assert required_events.issubset(event_types), f"Missing events: {required_events - event_types}"
    
    # Verify notifications
    notifications = client.get(f"/api/companies/{company_id}/notifications", headers=headers).json()
    notification_types = {n["notification_type"] for n in notifications}
    required_notifications = {"task_started", "task_submitted", "review_started", "review_completed", 
                              "submission_approved", "task_completed"}
    assert required_notifications.issubset(notification_types), f"Missing notifications: {required_notifications - notification_types}"
    
    # Verify activity log
    activity = client.get(f"/api/companies/{company_id}/activity", headers=headers).json()
    actions = {a["action"] for a in activity}
    required_actions = {"task_started", "task_submitted", "ai_review_completed", "manager_review_completed"}
    assert required_actions.issubset(actions), f"Missing activity: {required_actions - actions}"
    
    # Verify submission versions persisted
    submissions = client.get(f"/api/projects/{project_id}/submissions", headers=headers).json()
    assert len(submissions) == 1
    submission = submissions[0]
    assert submission["current_version"] >= 1
    assert len(submission["versions"]) >= 1
    
    print("✅ Complete workflow test passed!")


def test_invalid_file_rejection():
    """Test that invalid files are rejected."""
    headers = {"Authorization": f"Bearer {make_token('student_invalid')}"}
    
    resp = client.post(
        "/api/generate",
        headers=headers,
        json={
            "student_id": "student_invalid",
            "role": "Backend Developer",
            "technology_stack": ["Python", "FastAPI"],
            "difficulty": "beginner",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    project_id = data["project_id"]
    
    board = client.get(f"/api/projects/{project_id}/board", headers=headers).json()
    task_id = next(t["id"] for status_list in board.values() for t in status_list if not t["depends_on_task_ids"])
    
    # Start task
    client.post(f"/api/projects/{project_id}/submissions/tasks/{task_id}/start", headers=headers)
    
    # Try to submit empty file
    files = {"files": ("empty.py", io.BytesIO(b""), "text/x-python")}
    resp = client.post(
        f"/api/projects/{project_id}/submissions/tasks/{task_id}/submit",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 400
    assert "Empty files are not allowed" in resp.json()["detail"]
    
    # Try to submit invalid extension
    files = {"files": ("script.exe", io.BytesIO(b"malicious"), "application/x-msdownload")}
    resp = client.post(
        f"/api/projects/{project_id}/submissions/tasks/{task_id}/submit",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]


def test_unauthorized_submission():
    """Test that students can't submit for other students' tasks."""
    headers1 = {"Authorization": f"Bearer {make_token('student_a')}"}
    headers2 = {"Authorization": f"Bearer {make_token('student_b')}"}
    
    # Student A creates project
    resp = client.post(
        "/api/generate",
        headers=headers1,
        json={
            "student_id": "student_a",
            "role": "Backend Developer",
            "technology_stack": ["Python", "FastAPI"],
            "difficulty": "beginner",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    project_id = data["project_id"]
    
    board = client.get(f"/api/projects/{project_id}/board", headers=headers1).json()
    task_id = next(t["id"] for status_list in board.values() for t in status_list if not t["depends_on_task_ids"])
    
    # Student B tries to submit for student A's task
    client.post(f"/api/projects/{project_id}/submissions/tasks/{task_id}/start", headers=headers1)
    files = {"files": ("main.py", io.BytesIO(b"print('hello')"), "text/x-python")}
    resp = client.post(
        f"/api/projects/{project_id}/submissions/tasks/{task_id}/submit",
        headers=headers2,
        files=files,
    )
    assert resp.status_code == 403
    assert "Not your" in resp.json()["detail"]


def test_invalid_state_transition():
    """Test that invalid state transitions are rejected."""
    headers = {"Authorization": f"Bearer {make_token('student_transition')}"}
    
    resp = client.post(
        "/api/generate",
        headers=headers,
        json={
            "student_id": "student_transition",
            "role": "Backend Developer",
            "technology_stack": ["Python"],
            "difficulty": "beginner",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    project_id = data["project_id"]
    
    board = client.get(f"/api/projects/{project_id}/board", headers=headers).json()
    task_id = next(t["id"] for status_list in board.values() for t in status_list if not t["depends_on_task_ids"])
    
    # Try to complete without starting
    resp = client.patch(
        f"/api/tasks/{task_id}/status",
        headers=headers,
        json={"status": "completed"},
    )
    assert resp.status_code == 400
    assert "Invalid transition" in resp.json()["detail"]


def test_blocked_task_dependency():
    """Test that tasks with incomplete dependencies cannot be started."""
    headers = {"Authorization": f"Bearer {make_token('student_dep')}"}
    
    resp = client.post(
        "/api/generate",
        headers=headers,
        json={
            "student_id": "student_dep",
            "role": "Backend Developer",
            "technology_stack": ["Python"],
            "difficulty": "beginner",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    project_id = data["project_id"]
    
    board = client.get(f"/api/projects/{project_id}/board", headers=headers).json()
    dependent = next(t for status_list in board.values() for t in status_list if t["depends_on_task_ids"])
    anchor_id = dependent["depends_on_task_ids"][0]
    
    # Try to start dependent task without completing anchor
    resp = client.post(
        f"/api/projects/{project_id}/submissions/tasks/{dependent['id']}/start",
        headers=headers,
    )
    assert resp.status_code == 409
    assert "dependencies are not completed" in resp.json()["detail"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])