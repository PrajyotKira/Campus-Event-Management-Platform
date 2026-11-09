"""Tests for the report numbers. These must give the same answers before and
after the performance optimisation, which is what proves the faster version is correct."""
import pytest
from werkzeug.security import generate_password_hash

from app import reports
from app.db import add_indexes, get_db


@pytest.fixture
def report_data(app, sample_events):
    """sample_events (4 events, all at 'Seminar Hall A', capacity 100) plus:
    - an empty second venue, 'Empty Hall'
    - registrations: Python Workshop 3, Old Python Talk 2, Football Match 1, Hackathon 0
    """
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO venues (name, capacity, location) VALUES ('Empty Hall', 50, 'Block 2')"
        )
        password_hash = generate_password_hash("x")
        student_ids = [
            conn.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'student')",
                (f"Student {i}", f"s{i}@test.com", password_hash),
            ).lastrowid
            for i in range(3)
        ]
        plan = {"Python Workshop": 3, "Old Python Talk": 2, "Football Match": 1}
        for title, how_many in plan.items():
            for user_id in student_ids[:how_many]:
                conn.execute(
                    "INSERT INTO registrations (user_id, event_id) VALUES (?, ?)",
                    (user_id, sample_events[title]),
                )
        conn.commit()


def test_percent():
    assert reports.percent(3, 30) == 10.0
    assert reports.percent(1, 3) == 33.3
    assert reports.percent(5, 0) == 0.0  # no division by zero


def test_event_stats(app, report_data):
    with app.app_context():
        stats = reports.event_stats()

    # (title, registered, capacity, fill rate), most registrations first.
    assert [(s["title"], s["registered"], s["capacity"], s["fill_rate"]) for s in stats] == [
        ("Python Workshop", 3, 30, 10.0),
        ("Old Python Talk", 2, 40, 5.0),
        ("Football Match", 1, 50, 2.0),
        ("Hackathon", 0, 40, 0.0),
    ]


def test_popular_categories(app, report_data):
    with app.app_context():
        categories = reports.popular_categories()

    assert categories == [
        {"category": "Workshop", "events": 1, "registrations": 3},
        {"category": "Seminar", "events": 1, "registrations": 2},
        {"category": "Sports", "events": 1, "registrations": 1},
        {"category": "Technical", "events": 1, "registrations": 0},
    ]


def test_venue_utilisation(app, report_data):
    with app.app_context():
        venues = reports.venue_utilisation()

    # (name, events, registrations, seats offered, utilisation %)
    assert [(v["name"], v["events"], v["registrations"], v["seats_offered"], v["utilisation"])
            for v in venues] == [
        ("Seminar Hall A", 4, 6, 160, 3.8),   # 6 of 30+50+40+40 seats
        ("Empty Hall", 0, 0, 0, 0.0),         # venues with no events are still listed
    ]


def test_indexes_do_not_change_report_numbers(app, report_data):
    """Indexes only change HOW SQLite finds rows, never the answers."""
    with app.app_context():
        without_indexes = (reports.event_stats(), reports.popular_categories(),
                           reports.venue_utilisation())
        add_indexes()
        names = {row["name"] for row in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )}
        with_indexes = (reports.event_stats(), reports.popular_categories(),
                        reports.venue_utilisation())

    assert {"idx_registrations_event", "idx_events_venue_start",
            "idx_events_category"} <= names  # <= on sets means "is a subset of"
    assert with_indexes == without_indexes


def test_reports_page_shows_numbers(admin_client, report_data):
    response = admin_client.get("/admin/reports")

    assert response.status_code == 200
    assert b"Python Workshop" in response.data
    assert b"10.0%" in response.data
    assert b"Empty Hall" in response.data


def test_student_cannot_open_reports(student_client):
    assert student_client.get("/admin/reports").status_code == 403
