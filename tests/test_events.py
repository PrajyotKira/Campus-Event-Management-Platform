"""Tests for the event list, search filters and detail page."""
from app.db import get_db


def test_event_list_shows_only_upcoming_events(client, sample_events):
    response = client.get("/events/")

    assert response.status_code == 200
    assert b"Python Workshop" in response.data
    assert b"Football Match" in response.data
    assert b"Old Python Talk" not in response.data  # past event is hidden


def test_keyword_search_returns_only_matching_events(client, sample_events):
    response = client.get("/events/?q=python")

    # Matches the title (case-insensitive) and the description.
    assert b"Python Workshop" in response.data
    assert b"Hackathon" in response.data
    # Does not match, or is in the past.
    assert b"Football Match" not in response.data
    assert b"Old Python Talk" not in response.data


def test_category_filter(client, sample_events):
    response = client.get("/events/?category=Sports")

    assert b"Football Match" in response.data
    assert b"Python Workshop" not in response.data


def test_seats_left_counts_registrations(client, app, sample_events, auth):
    auth.register()
    with app.app_context():
        conn = get_db()
        student_id = conn.execute("SELECT id FROM users WHERE role = 'student'").fetchone()[0]
        event_id = conn.execute(
            "SELECT id FROM events WHERE title = 'Python Workshop'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO registrations (user_id, event_id) VALUES (?, ?)",
            (student_id, event_id),
        )
        conn.commit()

    response = client.get(f"/events/{event_id}")
    assert b"29 of 30 left" in response.data  # capacity 30, one registration


def test_missing_event_returns_404(client):
    response = client.get("/events/9999")
    assert response.status_code == 404
