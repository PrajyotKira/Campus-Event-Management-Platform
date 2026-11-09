"""Tests for registering, logging in and admin-only access."""
from app.db import get_db


def test_register_creates_student(client, auth, app):
    response = auth.register()

    # After registering, the user is redirected (302) to the login page.
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    # The account is saved as a student, and the password is stored hashed.
    with app.app_context():
        user = get_db().execute(
            "SELECT role, password_hash FROM users WHERE email = ?", ("student@test.com",)
        ).fetchone()
    assert user is not None
    assert user["role"] == "student"
    assert user["password_hash"] != "secret123"


def test_duplicate_email_rejected(client, auth, app):
    auth.register()
    response = auth.register(name="Someone Else")  # same email again

    assert b"already exists" in response.data
    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", ("student@test.com",)
        ).fetchone()[0]
    assert count == 1


def test_login_with_correct_password_works(client, auth):
    auth.register()
    response = auth.login()

    assert response.status_code == 302
    # The nav now shows Logout, so we are logged in.
    page = client.get("/events/")
    assert b"Logout" in page.data


def test_login_with_wrong_password_fails(client, auth):
    auth.register()
    response = auth.login(password="wrong-password")

    assert response.status_code == 200  # stays on the login page
    assert b"Invalid email or password" in response.data
    # Not logged in: the nav still offers Login and there is no Logout link.
    page = client.get("/events/")
    assert b"Logout" not in page.data


def test_student_gets_403_on_admin_route(client, auth):
    auth.register()
    auth.login()

    response = client.get("/admin/")
    assert response.status_code == 403


def test_admin_can_open_admin_route(client, auth, admin_user):
    auth.login(email=admin_user["email"], password=admin_user["password"])

    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Admin dashboard" in response.data


def test_logged_out_user_is_sent_to_login_from_admin_route(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
