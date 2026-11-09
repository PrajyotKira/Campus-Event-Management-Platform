# CLAUDE.md: Campus Event Management Platform

Solo college project, **due 16 Nov 2026**. The student must be able to explain
every line in a viva, so keep code **simple, readable and well commented**.
No over-engineering, no clever abstractions.

## Hard rules
- **Never run `git commit`** (or push). The student makes every commit themselves.
  Suggest small commits with `feat:` / `fix:` / `chore:` / `docs:` / `test:` prefixes instead.
- **Raw SQL only** via Python's built-in `sqlite3` (no ORM, the SQL is graded).
  Always use `?` placeholders, never string formatting.
- Indexes live in `sql/indexes.sql` (not schema.sql); they were the profiling optimisation.
  Keep `profiling/before/` untouched: it is the evidence of the naive version.
- Hand-written CSS only (no Bootstrap/Tailwind/JS frameworks).
- Log AI help in `AI_USAGE.md` (Date | Tool | What AI did | What I changed/verified).

## Graded requirements
Course modules: HTML/CSS, Python, SQL, Git, Bash. Also: meaningful git history,
README (topics covered, installation, usage), Bash automation scripts, pytest
functional tests, cProfile profiling with before/after, LaTeX report + Beamer slides.

## Stack
Python 3, Flask, Flask-Login, Werkzeug password hashing, SQLite (sqlite3, raw SQL),
Jinja2 templates, pytest, Faker (seed data), cProfile.

## Environment
Windows + Git Bash. Bash scripts must:
- use `set -euo pipefail` and clear `echo` messages
- activate venv from `venv/Scripts/activate` (Windows) or `venv/bin/activate` (Linux/Mac)
- use `python3` or `python`, whichever actually runs (on this machine `python3` is the
  broken Microsoft Store stub, so test by running `--version`, not `command -v`)
- shared helpers live in `scripts/common.sh`

## Layout
```
app/            __init__.py (app factory), db.py, auth.py, events.py, admin.py,
                templates/, static/style.css
sql/schema.sql  tables: users, venues, events, registrations
scripts/        common.sh, setup.sh, run.sh, seed.sh, test.sh, profile.sh
tests/  profiling/  report/
instance/       campus.db lives here (git-ignored)
```
Flask CLI commands (always run as `python -m flask --app app ...`; the `flask.exe`
launcher is blocked on this machine): `init-db`, `create-admin` (in `app/db.py`),
`seed --events N --students M` (in `app/seed.py`, fixed random seed, keeps admins).

Blueprints:
- `auth`: /auth/register, /auth/login, /auth/logout; defines `admin_required`.
- `events` (no url_prefix): /events/, /events/<id>, POST /events/<id>/register,
  POST /events/<id>/cancel (form field return_to=my), /my-registrations.
- `admin` (/admin, all @admin_required): dashboard, venues CRUD, events CRUD,
  /admin/events/<id>/participants and participants.csv. `find_clash()`,
  `read_event_form()`, `read_venue_form()`, `to_db_time()` are plain helpers there.
All data-changing actions are POST forms; `SESSION_COOKIE_SAMESITE="Lax"` in config.
Times are stored as TEXT 'YYYY-MM-DD HH:MM'. `CATEGORIES` list lives in `app/events.py`.

Demo logins after `./scripts/setup.sh && ./scripts/seed.sh`:
admin `admin@campus.local` / `admin123`, students `student1..100@campus.local` / `student123`.

Profiling: `./scripts/profile.sh <label> [events=2000]` (env vars RUNS=3, APPLY_INDEXES=1)
builds a separate DB `profiling/profile.db` via the `CAMPUS_DB` env var (read in create_app),
seeds it, adds indexes, then runs `python -m profiling.run_profile <label> <runs>` and
`python -m profiling.explain <label>`. Output in profiling/<label>/: profile.prof (view with
`snakeviz`), profile_stats.txt (top 20 cumulative), timings.txt, query_plans.txt.
`build_search_sql()` / `search_events()` in events.py are plain functions so they can be
profiled and EXPLAINed. Indexes are NOT part of schema.sql / init_db (tests run without them,
plus one test that applies them).

Tests: `pytest.ini` sets `pythonpath = .`; fixtures in `tests/conftest.py`
(`app` on a tmp_path DB, `client`, `auth`, `admin_user`, `sample_events` -> {title: id},
`student_client`, `admin_client`). Test files: test_auth, test_events,
test_registrations, test_admin (38 tests at end of phase 3).
Gotcha: Jinja parses `{% %}` even inside HTML `<!-- -->` comments, so use `{# #}`.

## Features (planned)
- Student: register/login, browse events, search/filter (keyword, category, date, venue),
  register/cancel with capacity check, "My registrations".
- Admin: CRUD events & venues, reject venue time clashes (same venue, overlapping times:
  `new.start < existing.end AND new.end > existing.start`), participant list + CSV export,
  reports (registrations per event, fill rate %, popular categories, venue utilisation).

## Progress
- [x] Phase 1: skeleton, schema, setup/run scripts, app factory, homepage
- [x] Phase 2: auth (Flask-Login, admin_required), events browse/search/detail,
      seed.sh (Faker), first pytest tests + test.sh, placeholder admin dashboard
- [x] Phase 3: student register/cancel (full / started / duplicate checks) + My registrations;
      admin dashboard counts, venues & events CRUD, clash check, participants + CSV export;
      tests for all of it
- [x] Phase 4 Part A: /admin/reports using app/reports.py, written NAIVELY on purpose
      (N+1: one COUNT query per event); test_reports.py; profile.sh + profiling/run_profile.py;
      baseline saved in profiling/before/ (2000 events, 67,423 registrations:
      each report ~2000 SQL calls, ~3.5 s; search ~60 ms for 3 searches)
- [x] Phase 4 Part B: reports.py rewritten as one JOIN + GROUP BY query each (SQL in
      module constants; `percent()` stays in Python); sql/indexes.sql (registrations.event_id,
      events(venue_id, start_time), events.category; NOT registrations.user_id because the
      UNIQUE(user_id, event_id) autoindex already covers it) applied via `flask add-indexes`
      in setup.sh and profile.sh; profiling/explain.py; results in profiling/after/,
      profiling/rewrite_only/ and profiling/RESULTS.md (total 10,916 ms -> 32.6 ms, ~335x;
      SQL calls 6016 -> 6). 45 tests.
- [ ] Phase 5: README, LaTeX report, Beamer slides
