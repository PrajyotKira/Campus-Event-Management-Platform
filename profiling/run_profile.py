"""Profile the report functions and the event search with cProfile.

Normally run by scripts/profile.sh, which first builds a big seeded database:
    python -m profiling.run_profile <label> [runs]

For each "workload" (a function we want to measure) it:
  1. runs it several times WITHOUT the profiler and records the wall-clock time
     (cProfile slows Python down, so these are the honest timings) and counts
     how many SQL statements one run sends to SQLite;
  2. runs it once more WITH cProfile switched on, to see where the time goes.

Results are saved in profiling/<label>/:
  profile.prof        raw cProfile data (open with: snakeviz profiling/<label>/profile.prof)
  profile_stats.txt   top 20 functions sorted by cumulative time
  timings.txt         wall-clock times and SQL statement counts per workload
"""
import cProfile
import os
import pstats
import sys
import time
from datetime import datetime, timedelta

from app import create_app, reports
from app.db import get_db
from app.events import search_events


def run_searches():
    """Three typical searches a student might do on the events page."""
    today = datetime.now()
    search_events()                         # no filters: every upcoming event
    search_events(keyword="workshop")       # keyword search (LIKE)
    search_events(                          # category dropdown + date range
        category="Sports",
        date_from=today.strftime("%Y-%m-%d"),
        date_to=(today + timedelta(days=30)).strftime("%Y-%m-%d"),
    )


# (name shown in the results, function to call)
WORKLOADS = [
    ("event_stats", reports.event_stats),
    ("popular_categories", reports.popular_categories),
    ("venue_utilisation", reports.venue_utilisation),
    ("search_events (3 searches)", run_searches),
]


def main():
    # Command-line arguments: sys.argv[0] is the script itself.
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    out_dir = os.path.join("profiling", label)
    os.makedirs(out_dir, exist_ok=True)

    app = create_app()
    # The report functions call get_db(), which needs an app context.
    with app.app_context():
        conn = get_db()
        sizes = conn.execute(
            "SELECT (SELECT COUNT(*) FROM events), (SELECT COUNT(*) FROM registrations), "
            "       (SELECT COUNT(*) FROM venues)"
        ).fetchone()

        # SQLite calls this function once for every SQL statement it runs.
        sql_counter = {"count": 0}

        def count_statement(statement):
            sql_counter["count"] += 1

        profiler = cProfile.Profile()
        results = []  # (name, sql statements per run, fastest seconds, average seconds)

        for name, function in WORKLOADS:
            print(f"    {name} ...", flush=True)

            # 1. Timed runs, profiler OFF, counting SQL statements.
            conn.set_trace_callback(count_statement)
            times = []
            for _ in range(runs):
                sql_counter["count"] = 0
                start = time.perf_counter()
                function()
                times.append(time.perf_counter() - start)
            conn.set_trace_callback(None)  # stop counting

            # 2. One extra run with the profiler ON (adds to the same profile).
            profiler.enable()
            function()
            profiler.disable()

            results.append((name, sql_counter["count"], min(times), sum(times) / len(times)))

    # ---- Save the results ----
    profiler.dump_stats(os.path.join(out_dir, "profile.prof"))

    with open(os.path.join(out_dir, "profile_stats.txt"), "w", encoding="utf-8") as f:
        f.write(f"cProfile results ({label}): one profiled run of each workload\n\n")
        stats = pstats.Stats(profiler, stream=f)
        # strip_dirs: shorter names; cumulative: time inside a function INCLUDING what it calls.
        stats.strip_dirs().sort_stats("cumulative").print_stats(20)

    lines = [
        f"Profile: {label}   ({datetime.now():%Y-%m-%d %H:%M})",
        f"Data: {sizes[0]} events, {sizes[1]} registrations, {sizes[2]} venues",
        f"Each workload was timed {runs} times without the profiler.",
        "",
        f"{'Workload':<28} {'SQL calls':>10} {'Fastest (ms)':>13} {'Average (ms)':>13}",
        "-" * 67,
    ]
    for name, sql_calls, fastest, average in results:
        lines.append(f"{name:<28} {sql_calls:>10} {fastest * 1000:>13.1f} {average * 1000:>13.1f}")
    total = sum(r[3] for r in results)
    lines.append("-" * 67)
    lines.append(f"{'Total (average)':<28} {'':>10} {'':>13} {total * 1000:>13.1f}")

    summary = "\n".join(lines)
    with open(os.path.join(out_dir, "timings.txt"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")

    print()
    print(summary)
    print()
    print(f"Saved in profiling/{label}/: profile.prof, profile_stats.txt, timings.txt")


if __name__ == "__main__":
    main()
