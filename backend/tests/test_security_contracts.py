from fastapi.testclient import TestClient

from pharma_management.db import SessionLocal
from pharma_management.main import app
from pharma_management.models import User, UserRole
from pharma_management.security import hash_password


def test_login_lockout_after_repeated_failures() -> None:
    db = SessionLocal()
    email = "lockout-contract-test@example.com"
    user = User(email=email, full_name="Lockout Test", password_hash=hash_password("CorrectPassword!123"), role=UserRole.VIEWER)
    db.add(user)
    db.commit()
    client = TestClient(app)
    try:
        for _ in range(5):
            response = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword!123"})
            assert response.status_code == 401
        db.refresh(user)
        assert user.locked_until is not None
        response = client.post("/api/v1/auth/login", json={"email": email, "password": "CorrectPassword!123"})
        assert response.status_code == 401
    finally:
        db.delete(user)
        db.commit()
        db.close()


def test_logout_revokes_server_side_session() -> None:
    db = SessionLocal()
    email = "session-contract-test@example.com"
    user = User(email=email, full_name="Session Test", password_hash=hash_password("CorrectPassword!123"), role=UserRole.VIEWER)
    db.add(user)
    db.commit()
    client = TestClient(app)
    try:
        login = client.post("/api/v1/auth/login", json={"email": email, "password": "CorrectPassword!123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    finally:
        db.delete(user)
        db.commit()
        db.close()
