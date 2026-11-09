# AI Usage Log

A record of where AI tools helped in this project, and what I checked or changed myself.

| Date | Tool | What AI did | What I changed/verified |
|------|------|-------------|-------------------------|
| 2026-11-09 | Claude Code | Phase 1 scaffold: folder structure, `sql/schema.sql`, `scripts/setup.sh`, `scripts/run.sh`, `scripts/common.sh`, Flask app factory, `db.py`, base template and CSS, CLAUDE.md | _(fill in: e.g. ran setup.sh and run.sh in Git Bash, read through the schema, changed ...)_ |
| 2026-11-09 | Claude Code | Phase 2: `auth.py` (register/login/logout, `admin_required`), `events.py` (list with safe search filters, detail page), placeholder `admin.py`, `seed.py` + `seed.sh`, pytest fixtures and 12 tests, `test.sh`, templates and CSS | _(fill in: e.g. ran test.sh, tried logging in as student and admin, read the WHERE-clause builder, changed ...)_ |
| 2026-11-09 | Claude Code | Phase 3: register/cancel routes and My registrations page; admin dashboard, venue and event CRUD with validation and `find_clash()`; participants page and CSV export; 26 new tests (registrations, clashes, capacity, access control, CSV) | _(fill in: e.g. ran test.sh, created/edited/deleted an event in the browser, tried a clashing booking, opened the CSV in Excel, changed ...)_ |
| 2026-11-09 | Claude Code | Phase 4 Part A: naive (N+1) report functions in `app/reports.py` and the reports page, report tests, `search_events()` extracted for profiling, `profiling/run_profile.py` and `scripts/profile.sh`, baseline profile in `profiling/before/` | _(fill in: e.g. ran profile.sh before, opened profile.prof in snakeviz, checked the report numbers by hand, changed ...)_ |
