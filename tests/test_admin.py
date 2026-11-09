"""Tests for admin venue/event management, the clash check and the CSV export."""
import csv
import io
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.admin import find_clash
from app.db import get_db


def get_event(app, event_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()


def count_events(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM events").fetchone()[0]


def event_form(event, **changes):
    """Form data for an event, based on an existing row, with some fields changed.

    The form uses datetime-local format ('YYYY-MM-DDTHH:MM'), so swap space for T.
    """
    data = {
        "title": event["title"],
        "description": event["description"],
        "category": event["category"],
        "venue_id": event["venue_id"],
        "start_time": event["start_time"].replace(" ", "T"),
        "end_time": event["end_time"].replace(" ", "T"),
        "capacity": event["capacity"],
    }
    data.update(changes)
    return data


# ---------- The clash check function on its own ----------

def shift(time_string, minutes):
    """Move a 'YYYY-MM-DD HH:MM' time by some minutes (negative = earlier)."""
    moved = datetime.strptime(time_string, "%Y-%m-%d %H:%M") + timedelta(minutes=minutes)
    return moved.strftime("%Y-%m-%d %H:%M")


def test_find_clash(app, sample_events):
    workshop = get_event(app, sample_events["Python Workshop"])
    venue, start, end = workshop["venue_id"], workshop["start_time"], workshop["end_time"]

    with app.app_context():
        # Exactly the same time -> clash.
        assert find_clash(venue, start, end) is not None
        # Starts an hour before and ends 30 minutes into the workshop -> clash.
        assert find_clash(venue, shift(start, -60), shift(start, 30)) is not None
        # Inside the workshop -> clash.
        assert find_clash(venue, shift(start, 10), shift(start, 20)) is not None
        # Ends exactly when the workshop starts -> only touching, no clash.
        assert find_clash(venue, shift(start, -60), start) is None
        # Same time but a different venue -> no clash.
        assert find_clash(venue + 1, start, end) is None
        # Ignoring the workshop itself (as when editing it) -> no clash.
        assert find_clash(venue, start, end, ignore_event_id=workshop["id"]) is None


# ---------- Creating and editing events ----------

def test_create_event(app, admin_client, sample_events):
    workshop = get_event(app, sample_events["Python Workshop"])
    form = event_form(workshop, title="Robotics Demo",
                      start_time="2030-05-01T10:00", end_time="2030-05-01T12:00")

    response = admin_client.post("/admin/events/new", data=form, follow_redirects=True)

    assert b"Robotics Demo&#39; created" in response.data
    with app.app_context():
        row = get_db().execute(
            "SELECT start_time, end_time FROM events WHERE title = 'Robotics Demo'"
        ).fetchone()
    # datetime-local values are stored in our 'YYYY-MM-DD HH:MM' format.
    assert row["start_time"] == "2030-05-01 10:00"
    assert row["end_time"] == "2030-05-01 12:00"


def test_venue_clash_rejected(app, admin_client, sample_events):
    workshop = get_event(app, sample_events["Python Workshop"])
    before = count_events(app)

    # A new event at the same venue and the same time as the workshop.
    response = admin_client.post("/admin/events/new",
                                 data=event_form(workshop, title="Clashing Event"))

    assert b"already booked" in response.data
    assert count_events(app) == before


def test_edit_does_not_clash_with_itself(app, admin_client, sample_events):
    event_id = sample_events["Python Workshop"]
    workshop = get_event(app, event_id)

    # Same venue and times, only the title changes.
    response = admin_client.post(f"/admin/events/{event_id}/edit",
                                 data=event_form(workshop, title="Python Workshop II"),
                                 follow_redirects=True)

    assert b"updated" in response.data
    assert get_event(app, event_id)["title"] == "Python Workshop II"


def test_capacity_over_venue_capacity_rejected(app, admin_client, sample_events):
    workshop = get_event(app, sample_events["Python Workshop"])  # venue holds 100
    form = event_form(workshop, title="Huge Event", capacity=500,
                      start_time="2030-05-01T10:00", end_time="2030-05-01T12:00")

    response = admin_client.post("/admin/events/new", data=form)

    assert b"cannot be more than the capacity" in response.data
    assert count_events(app) == 4


def test_end_before_start_rejected(app, admin_client, sample_events):
    workshop = get_event(app, sample_events["Python Workshop"])
    form = event_form(workshop, title="Backwards Event",
                      start_time="2030-05-01T12:00", end_time="2030-05-01T10:00")

    response = admin_client.post("/admin/events/new", data=form)

    assert b"must end after it starts" in response.data


def test_delete_event_removes_its_registrations(app, admin_client, sample_events):
    event_id = sample_events["Python Workshop"]
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO registrations (user_id, event_id) "
            "SELECT id, ? FROM users WHERE role = 'admin'", (event_id,)
        )
        conn.commit()

    admin_client.post(f"/admin/events/{event_id}/delete")

    assert get_event(app, event_id) is None
    with app.app_context():
        left = get_db().execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ?", (event_id,)
        ).fetchone()[0]
    assert left == 0  # removed by ON DELETE CASCADE


# ---------- Venues ----------

def test_create_venue(app, admin_client):
    response = admin_client.post(
        "/admin/venues/new",
        data={"name": "New Hall", "location": "Block 9", "capacity": "75"},
        follow_redirects=True,
    )
    assert b"New Hall" in response.data
    with app.app_context():
        row = get_db().execute("SELECT capacity FROM venues WHERE name = 'New Hall'").fetchone()
    assert row["capacity"] == 75


def test_venue_with_events_cannot_be_deleted(app, admin_client, sample_events):
    venue_id = get_event(app, sample_events["Python Workshop"])["venue_id"]

    response = admin_client.post(f"/admin/venues/{venue_id}/delete", follow_redirects=True)

    assert b"Cannot delete" in response.data
    with app.app_context():
        assert get_db().execute(
            "SELECT 1 FROM venues WHERE id = ?", (venue_id,)
        ).fetchone() is not None


# ---------- Students are kept out ----------

# parametrize runs this one test once for every URL in the list.
@pytest.mark.parametrize("url", [
    "/admin/venues",
    "/admin/venues/new",
    "/admin/events",
    "/admin/events/new",
    "/admin/events/1/edit",
    "/admin/events/1/participants",
    "/admin/events/1/participants.csv",
])
def test_student_cannot_open_admin_pages(student_client, sample_events, url):
    assert student_client.get(url).status_code == 403


def test_student_cannot_delete_event(app, student_client, sample_events):
    event_id = sample_events["Python Workshop"]

    response = student_client.post(f"/admin/events/{event_id}/delete")

    assert response.status_code == 403
    assert get_event(app, event_id) is not None


# ---------- Participants and CSV export ----------

def test_csv_export_returns_the_right_rows(app, admin_client, sample_events):
    workshop_id = sample_events["Python Workshop"]
    football_id = sample_events["Football Match"]
    with app.app_context():
        conn = get_db()
        password_hash = generate_password_hash("x")
        students = [("Asha", "asha@test.com"), ("Ravi", "ravi@test.com"), ("Meera", "meera@test.com")]
        ids = {}
        for name, email in students:
            ids[name] = conn.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'student')",
                (name, email, password_hash),
            ).lastrowid
        # Asha and Ravi go to the workshop; Meera goes to football only.
        conn.executemany(
            "INSERT INTO registrations (user_id, event_id, registered_at) VALUES (?, ?, ?)",
            [(ids["Asha"], workshop_id, "2026-11-01 10:00:00"),
             (ids["Ravi"], workshop_id, "2026-11-02 11:00:00"),
             (ids["Meera"], football_id, "2026-11-03 12:00:00")],
        )
        conn.commit()

    response = admin_client.get(f"/admin/events/{workshop_id}/participants.csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows == [
        ["Name", "Email", "Registered at"],
        ["Asha", "asha@test.com", "2026-11-01 10:00:00"],
        ["Ravi", "ravi@test.com", "2026-11-02 11:00:00"],
    ]
