"""Shared pytest fixtures. pytest loads this file automatically.

A fixture is a function that prepares something a test needs. A test asks for
it by using the fixture's name as a parameter, e.g. def test_x(client): ...
"""
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db, init_db


@pytest.fixture
def app(tmp_path):
    """A fresh app for each test, using an empty database in a temporary folder.

    tmp_path is a built-in pytest fixture: a new temporary folder per test.
    """
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE": str(tmp_path / "test.db"),
    })
    with app.app_context():
        init_db()  # runs sql/schema.sql on the test database
    yield app


@pytest.fixture
def client(app):
    """A fake browser that sends requests to the app without running a server."""
    return app.test_client()


class AuthActions:
    """Helpers so tests can register and log in with one line."""

    def __init__(self, client):
        self._client = client

    def register(self, name="Test Student", email="student@test.com", password="secret123"):
        return self._client.post(
            "/auth/register", data={"name": name, "email": email, "password": password}
        )

    def login(self, email="student@test.com", password="secret123"):
        return self._client.post(
            "/auth/login", data={"email": email, "password": password}
        )


@pytest.fixture
def auth(client):
    return AuthActions(client)


@pytest.fixture
def admin_user(app):
    """Insert an admin account directly with SQL (admins can't sign up)."""
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
            ("Test Admin", "admin@test.com", generate_password_hash("adminpass")),
        )
        conn.commit()
    return {"email": "admin@test.com", "password": "adminpass"}


def time_from_now(days):
    """A 'YYYY-MM-DD HH:MM' string this many days from now (negative = past)."""
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")


@pytest.fixture
def sample_events(app, admin_user):
    """A venue and a few events: three upcoming, one in the past.

    'Python Workshop' has "Python" in its title, 'Hackathon' only in its
    description, and the past event should never be listed.
    Returns a dict {title: event id} so tests can find each event.
    """
    ids = {}
    with app.app_context():
        conn = get_db()
        admin_id = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()[0]
        venue_id = conn.execute(
            "INSERT INTO venues (name, capacity, location) VALUES (?, ?, ?)",
            ("Seminar Hall A", 100, "Block 1"),
        ).lastrowid

        events = [
            ("Python Workshop", "Learn the basics of programming.", "Workshop", 2, 30),
            ("Football Match", "Inter-hostel final.", "Sports", 3, 50),
            ("Hackathon", "Build a project in Python overnight.", "Technical", 4, 40),
            ("Old Python Talk", "This one already happened.", "Seminar", -3, 40),
        ]
        for title, description, category, days, capacity in events:
            ids[title] = conn.execute(
                "INSERT INTO events (title, description, category, venue_id, "
                "start_time, end_time, capacity, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (title, description, category, venue_id,
                 time_from_now(days), time_from_now(days + 0.1), capacity, admin_id),
            ).lastrowid
        conn.commit()
    return ids


@pytest.fixture
def student_client(client, auth):
    """A test client that is logged in as a student."""
    auth.register()
    auth.login()
    return client


@pytest.fixture
def admin_client(client, auth, admin_user):
    """A test client that is logged in as the admin."""
    auth.login(email=admin_user["email"], password=admin_user["password"])
    return client
