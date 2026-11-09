"""Tests for students registering for and cancelling events."""
from werkzeug.security import generate_password_hash

from app.db import get_db


def count_registrations(app, event_id):
    with app.app_context():
        return get_db().execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ?", (event_id,)
        ).fetchone()[0]


def test_register_for_event(app, student_client, sample_events):
    event_id = sample_events["Python Workshop"]

    # follow_redirects=True: also load the page we get sent to, so we can read the flash message.
    response = student_client.post(f"/events/{event_id}/register", follow_redirects=True)

    assert b"You are registered" in response.data
    assert b"29 of 30 left" in response.data
    assert count_registrations(app, event_id) == 1


def test_double_registration_rejected(app, student_client, sample_events):
    event_id = sample_events["Python Workshop"]

    student_client.post(f"/events/{event_id}/register")
    response = student_client.post(f"/events/{event_id}/register", follow_redirects=True)

    assert b"already registered" in response.data
    assert count_registrations(app, event_id) == 1


def test_full_event_rejected(app, student_client, sample_events):
    event_id = sample_events["Python Workshop"]
    # Make the event hold 1 person, and give that seat to another student.
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE events SET capacity = 1 WHERE id = ?", (event_id,))
        other_id = conn.execute(
            "INSERT INTO users (name, email, password_hash, role) "
            "VALUES ('Other', 'other@test.com', ?, 'student')",
            (generate_password_hash("x"),),
        ).lastrowid
        conn.execute(
            "INSERT INTO registrations (user_id, event_id) VALUES (?, ?)", (other_id, event_id)
        )
        conn.commit()

    response = student_client.post(f"/events/{event_id}/register", follow_redirects=True)

    assert b"full" in response.data
    assert count_registrations(app, event_id) == 1  # still only the other student


def test_started_event_rejected(app, student_client, sample_events):
    event_id = sample_events["Old Python Talk"]  # 3 days in the past

    response = student_client.post(f"/events/{event_id}/register", follow_redirects=True)

    assert b"already started" in response.data
    assert count_registrations(app, event_id) == 0


def test_cancel_registration(app, student_client, sample_events):
    event_id = sample_events["Python Workshop"]
    student_client.post(f"/events/{event_id}/register")

    response = student_client.post(f"/events/{event_id}/cancel", follow_redirects=True)

    assert b"was cancelled" in response.data
    assert count_registrations(app, event_id) == 0


def test_my_registrations_lists_only_my_events(student_client, sample_events):
    student_client.post(f"/events/{sample_events['Python Workshop']}/register")

    response = student_client.get("/my-registrations")

    assert b"Python Workshop" in response.data
    assert b"Football Match" not in response.data


def test_cancel_from_my_registrations_returns_there(student_client, sample_events):
    event_id = sample_events["Python Workshop"]
    student_client.post(f"/events/{event_id}/register")

    response = student_client.post(f"/events/{event_id}/cancel", data={"return_to": "my"})

    assert response.headers["Location"].endswith("/my-registrations")


def test_must_be_logged_in_to_register(client, sample_events):
    response = client.post(f"/events/{sample_events['Python Workshop']}/register")
    assert "/auth/login" in response.headers["Location"]
