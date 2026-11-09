# AI Usage

**Tool:** Claude (Anthropic), used through the Claude Code extension in VS Code, November 2026.

Throughout the project, Claude drafted code, scripts, tests and documentation from my specifications and explained the code and concepts to me. I ran, tested and reviewed everything, and made every git commit myself.

| Phase | AI assistance | What I verified/changed |
|---|---|---|
| 1. Skeleton | Drafted folder structure, `sql/schema.sql`, `setup.sh`/`run.sh`/`common.sh`, app factory, `db.py`, base template and CSS; diagnosed the Windows `flask.exe` launcher issue (switched to `python -m flask`) and a Jinja comment bug | _(to fill in)_ |
| 2. Auth and browsing | Drafted login/register/logout and `admin_required`, event search and detail pages, Faker seed command and `seed.sh`, first 12 tests and `test.sh` | _(to fill in)_ |
| 3. Registrations and admin | Drafted register/cancel and My registrations, admin CRUD with validation and the venue clash check, participants page and CSV export, 26 tests | _(to fill in)_ |
| 4a. Naive reports and baseline | Drafted the naive (N+1) reports page and report tests, `profiling/run_profile.py` and `profile.sh` | _(to fill in)_ |
| 4b. Optimisation | Drafted the JOIN + GROUP BY rewrite, `sql/indexes.sql`, `profiling/explain.py` and `profiling/RESULTS.md`; suggested leaving out the redundant `registrations(user_id)` index | _(to fill in)_ |
| 5. Documentation | Drafted README, LaTeX report, Beamer slides and `build_docs.sh`; pointed out screenshots whose file names did not match their content | _(to fill in)_ |
