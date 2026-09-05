from app.core.security import hash_password
from app.models.user import User


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_user_without_permission_is_forbidden(client, db_session, seed_permission, seed_role):
    seed_permission("users.view", module="users")
    role = seed_role("No Access")
    user = User(
        email="noaccess@slphc.test",
        hashed_password=hash_password("Sup3rSecret!"),
        first_name="No",
        last_name="Access",
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()

    token = _login(client, "noaccess@slphc.test", "Sup3rSecret!")

    response = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_user_with_permission_is_allowed(client, db_session, seed_permission, seed_role):
    seed_permission("users.view", module="users")
    role = seed_role("Viewer", permission_codes=["users.view"])
    user = User(
        email="viewer@slphc.test",
        hashed_password=hash_password("Sup3rSecret!"),
        first_name="View",
        last_name="Er",
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()

    token = _login(client, "viewer@slphc.test", "Sup3rSecret!")

    response = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["total"] >= 1
