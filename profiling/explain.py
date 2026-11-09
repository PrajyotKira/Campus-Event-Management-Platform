"""Show how SQLite runs our important queries, using EXPLAIN QUERY PLAN.

Normally run by scripts/profile.sh:
    python -m profiling.explain <label>
Saves the plans to profiling/<label>/query_plans.txt.

How to read a plan:
  SCAN t                     reads EVERY row of table t (slow on big tables)
  SEARCH t USING INDEX i     jumps to matching rows through index i (fast)
  USING COVERING INDEX i     the index alone has every column needed, so the
                             table itself isn't even read (fastest)
  AUTOMATIC ... INDEX        SQLite builds a temporary index for this ONE query
                             and throws it away afterwards: a sign that a
                             permanent index is missing
  USE TEMP B-TREE            an extra sorting/grouping step
"""
import os
import sys
from datetime import datetime, timedelta

from app import create_app, reports
from app.db import get_db
from app.events import build_search_sql


def queries():
    """(title, sql, params) for every query we want to explain."""
    today = datetime.now()
    in_30_days = today + timedelta(days=30)
    plans = [
        ("Search: no filters", *build_search_sql()),
        ("Search: keyword 'workshop'", *build_search_sql(keyword="workshop")),
        ("Search: category + date range", *build_search_sql(
            category="Sports",
            date_from=today.strftime("%Y-%m-%d"),
            date_to=in_30_days.strftime("%Y-%m-%d"),
        )),
        ("Search: venue filter", *build_search_sql(venue_id=1)),
        # Copied from the first (naive) reports.py, which ran it once per event.
        ("Naive report: one COUNT per event (was run ~2000 times per report)",
         "SELECT COUNT(*) FROM registrations WHERE event_id = ?", (1,)),
        ("Report: event_stats", reports.EVENT_STATS_SQL, ()),
        ("Report: popular_categories", reports.CATEGORIES_SQL, ()),
        ("Report: venue_utilisation", reports.VENUES_SQL, ()),
        # Copied from admin.find_clash().
        ("Venue clash check",
         "SELECT id, title, start_time, end_time FROM events "
         "WHERE venue_id = ? AND start_time < ? AND end_time > ? LIMIT 1",
         (1, "2026-12-01 12:00", "2026-12-01 10:00")),
        # Copied from events.is_registered(): shows the UNIQUE constraint's own index.
        ("Is this student registered? (user_id lookup)",
         "SELECT 1 FROM registrations WHERE user_id = ? AND event_id = ?", (1, 1)),
    ]
    return plans


def format_plan(rows):
    """Turn EXPLAIN QUERY PLAN rows into an indented tree.

    Each row is (id, parent, notused, detail); parent tells us which step it belongs to.
    """
    depth = {0: -1}
    lines = []
    for row_id, parent, _notused, detail in rows:
        depth[row_id] = depth.get(parent, -1) + 1
        lines.append("    " + "  " * depth[row_id] + detail)
    return lines


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    out_dir = os.path.join("profiling", label)
    os.makedirs(out_dir, exist_ok=True)

    app = create_app()
    with app.app_context():
        conn = get_db()
        indexes = conn.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type = 'index' ORDER BY name"
        ).fetchall()

        lines = [f"Query plans ({label})", "", "Indexes in the database:"]
        for index in indexes:
            lines.append(f"    {index['name']}  (on {index['tbl_name']})")
        lines.append("")

        for title, sql, params in queries():
            rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
            lines.append(f"== {title}")
            lines.extend(format_plan(rows))
            lines.append("")

    text = "\n".join(lines)
    with open(os.path.join(out_dir, "query_plans.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
