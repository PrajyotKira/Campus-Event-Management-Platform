# CLAUDE.md: Campus Event Management Platform

Solo college project, **due 16 Nov 2026**. The student must be able to explain
every line in a viva, so keep code **simple, readable and well commented**.
No over-engineering, no clever abstractions.

## Hard rules
- **Never run `git commit`** (or push). The student makes every commit themselves.
  Suggest small commits with `feat:` / `fix:` / `chore:` / `docs:` / `test:` prefixes instead.
- **Raw SQL only** via Python's built-in `sqlite3` (no ORM, the SQL is graded).
  Always use `?` placeholders, never string formatting.
- **Do not add indexes** to `sql/schema.sql` yet. Adding indexes is the planned
  profiling optimisation (cProfile before/after).
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
DB CLI commands (in `app/db.py`): `flask --app app init-db`, `flask --app app create-admin`.

## Features (planned)
- Student: register/login, browse events, search/filter (keyword, category, date, venue),
  register/cancel with capacity check, "My registrations".
- Admin: CRUD events & venues, reject venue time clashes (same venue, overlapping times:
  `new.start < existing.end AND new.end > existing.start`), participant list + CSV export,
  reports (registrations per event, fill rate %, popular categories, venue utilisation).

## Progress
- [x] Phase 1: skeleton, schema, setup/run scripts, app factory, homepage
- [ ] Phase 2: auth (Flask-Login), events browse/search, registrations
- [ ] Phase 3: admin CRUD, clash check, CSV export, reports
- [ ] Phase 4: seed.sh (Faker), tests (pytest), test.sh
- [ ] Phase 5: profiling (cProfile) + indexes, before/after
- [ ] Phase 6: README, LaTeX report, Beamer slides
