"""Report calculations for the admin reports page.

These are plain functions (not routes) so tests and the profiler can call them
directly inside an app context.

OPTIMISED version. The first (naive) version fetched all events and then ran
one COUNT query per event in a Python loop: 2000 events meant 2001 queries
(the "N+1 query problem"). Now each report is ONE query that uses
JOIN + GROUP BY, so the database does all the counting in a single pass.
See profiling/RESULTS.md for the before/after measurements.

The SQL is kept in module-level constants so profiling/explain.py can show
the query plan for exactly the same queries.
"""
from .db import get_db


def percent(part, whole):
    """part as a percentage of whole, rounded to 1 decimal place (0 if whole is 0).

    Done in Python (not SQL ROUND) so the numbers are rounded exactly as in the
    first version: Python and SQLite round halves differently (12.25 -> 12.2 vs 12.3).
    """
    if whole == 0:
        return 0.0
    return round(100 * part / whole, 1)


# One row per event. LEFT JOIN keeps events with no registrations (COUNT(r.id) = 0).
EVENT_STATS_SQL = """
SELECT e.id, e.title, e.category, e.start_time, e.capacity,
       COUNT(r.id) AS registered
FROM events e
LEFT JOIN registrations r ON r.event_id = e.id
GROUP BY e.id
ORDER BY registered DESC, e.start_time, e.id
"""

# One row per category. The JOIN repeats each event once per registration,
# so we count DISTINCT event ids to count each event only once.
CATEGORIES_SQL = """
SELECT e.category,
       COUNT(DISTINCT e.id) AS events,
       COUNT(r.id) AS registrations
FROM events e
LEFT JOIN registrations r ON r.event_id = e.id
GROUP BY e.category
ORDER BY registrations DESC, e.category
"""

# One row per venue. The inner query (a "derived table") first counts the
# registrations of each event; the outer query then adds those up per venue.
# Doing it in two steps stops SUM(capacity) from being multiplied by the
# number of registrations. LEFT JOIN keeps venues with no events.
VENUES_SQL = """
SELECT v.id, v.name, v.location,
       COUNT(e.id) AS events,
       COALESCE(SUM(e.registered), 0) AS registrations,
       COALESCE(SUM(e.capacity), 0) AS seats_offered
FROM venues v
LEFT JOIN (
    SELECT ev.id, ev.venue_id, ev.capacity, COUNT(r.id) AS registered
    FROM events ev
    LEFT JOIN registrations r ON r.event_id = ev.id
    GROUP BY ev.id
) AS e ON e.venue_id = v.id
GROUP BY v.id
ORDER BY registrations DESC, v.name
"""


def event_stats():
    """Registrations and fill rate for every event, most registrations first.

    Returns a list of dicts: id, title, category, start_time, capacity,
    registered, fill_rate.
    """
    stats = []
    for row in get_db().execute(EVENT_STATS_SQL).fetchall():
        event = dict(row)  # sqlite3.Row -> normal dict so we can add a key
        event["fill_rate"] = percent(event["registered"], event["capacity"])
        stats.append(event)
    return stats


def popular_categories():
    """Number of events and registrations per category, most registrations first.

    Returns a list of dicts: category, events, registrations.
    """
    return [dict(row) for row in get_db().execute(CATEGORIES_SQL).fetchall()]


def venue_utilisation():
    """For every venue: events held, registrations, seats offered and utilisation %.

    Seats offered = total capacity of the venue's events.
    Utilisation = registrations as a percentage of seats offered.
    Returns a list of dicts: id, name, location, events, registrations,
    seats_offered, utilisation. Busiest venue first.
    """
    results = []
    for row in get_db().execute(VENUES_SQL).fetchall():
        venue = dict(row)
        venue["utilisation"] = percent(venue["registrations"], venue["seats_offered"])
        results.append(venue)
    return results
