from app.core.security import hash_password
from app.models.user import User


def _create_user(db_session, *, email="officer@slphc.test", password="Sup3rSecret!", roles=None):
    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name="Test",
        last_name="Officer",
        roles=roles or [],
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_login_succeeds_with_correct_credentials(client, db_session):
    _create_user(db_session, email="a@slphc.test", password="Sup3rSecret!")

    response = client.post("/api/auth/login", json={"email": "a@slphc.test", "password": "Sup3rSecret!"})

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "slphc_refresh_token" in response.cookies


def test_login_fails_with_wrong_password(client, db_session):
    _create_user(db_session, email="b@slphc.test", password="Sup3rSecret!")

    response = client.post("/api/auth/login", json={"email": "b@slphc.test", "password": "wrong"})

    assert response.status_code == 401


def test_account_locks_after_max_failed_attempts(client, db_session):
    _create_user(db_session, email="c@slphc.test", password="Sup3rSecret!")

    for _ in range(5):
        client.post("/api/auth/login", json={"email": "c@slphc.test", "password": "wrong"})

    response = client.post("/api/auth/login", json={"email": "c@slphc.test", "password": "Sup3rSecret!"})
    assert response.status_code == 423


def test_me_requires_bearer_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_refresh_rotates_token(client, db_session):
    _create_user(db_session, email="d@slphc.test", password="Sup3rSecret!")
    login = client.post("/api/auth/login", json={"email": "d@slphc.test", "password": "Sup3rSecret!"})
    old_refresh_cookie = login.cookies["slphc_refresh_token"]

    refresh = client.post("/api/auth/refresh")

    assert refresh.status_code == 200
    assert refresh.cookies["slphc_refresh_token"] != old_refresh_cookie
