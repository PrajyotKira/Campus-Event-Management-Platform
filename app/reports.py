"""Report calculations for the admin reports page.

These are plain functions (not routes) so tests and the profiler can call them
directly inside an app context.

NOTE: this is the deliberately NAIVE version. Each function first fetches a list
of rows, then runs one more COUNT query per row inside a Python loop. With N
events that is N + 1 queries: the "N+1 query problem". It gives the right
answers but gets slow as the data grows. profiling/run_profile.py measures it.
"""
from .db import get_db


def percent(part, whole):
    """part as a percentage of whole, rounded to 1 decimal place (0 if whole is 0)."""
    if whole == 0:
        return 0.0
    return round(100 * part / whole, 1)


def count_registrations(event_id):
    """How many students registered for one event. ONE SQL query per call."""
    return get_db().execute(
        "SELECT COUNT(*) FROM registrations WHERE event_id = ?", (event_id,)
    ).fetchone()[0]


def event_stats():
    """Registrations and fill rate for every event, most registrations first.

    Returns a list of dicts: id, title, category, start_time, capacity,
    registered, fill_rate.
    """
    events = get_db().execute(
        "SELECT id, title, category, start_time, capacity FROM events"
    ).fetchall()

    stats = []
    for event in events:
        registered = count_registrations(event["id"])  # N+1: one query per event
        stats.append({
            "id": event["id"],
            "title": event["title"],
            "category": event["category"],
            "start_time": event["start_time"],
            "capacity": event["capacity"],
            "registered": registered,
            "fill_rate": percent(registered, event["capacity"]),
        })

    # Most registrations first; ties broken by start time, then id.
    stats.sort(key=lambda s: (-s["registered"], s["start_time"], s["id"]))
    return stats


def popular_categories():
    """Number of events and registrations per category, most registrations first.

    Returns a list of dicts: category, events, registrations.
    """
    events = get_db().execute("SELECT id, category FROM events").fetchall()

    totals = {}  # category name -> {"category": ..., "events": ..., "registrations": ...}
    for event in events:
        if event["category"] not in totals:
            totals[event["category"]] = {
                "category": event["category"], "events": 0, "registrations": 0,
            }
        totals[event["category"]]["events"] += 1
        totals[event["category"]]["registrations"] += count_registrations(event["id"])  # N+1

    return sorted(totals.values(), key=lambda c: (-c["registrations"], c["category"]))


def venue_utilisation():
    """For every venue: events held, registrations, seats offered and utilisation %.

    Seats offered = total capacity of the venue's events.
    Utilisation = registrations as a percentage of seats offered.
    Returns a list of dicts: id, name, location, events, registrations,
    seats_offered, utilisation. Busiest venue first.
    """
    conn = get_db()
    venues = conn.execute("SELECT id, name, location FROM venues").fetchall()

    results = []
    for venue in venues:
        # One query per venue to get its events...
        events = conn.execute(
            "SELECT id, capacity FROM events WHERE venue_id = ?", (venue["id"],)
        ).fetchall()
        registrations = 0
        seats_offered = 0
        for event in events:
            registrations += count_registrations(event["id"])  # ...and one per event
            seats_offered += event["capacity"]
        results.append({
            "id": venue["id"],
            "name": venue["name"],
            "location": venue["location"],
            "events": len(events),
            "registrations": registrations,
            "seats_offered": seats_offered,
            "utilisation": percent(registrations, seats_offered),
        })

    results.sort(key=lambda v: (-v["registrations"], v["name"]))
    return results
