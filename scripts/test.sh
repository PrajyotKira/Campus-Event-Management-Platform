#!/usr/bin/env bash
# Run the automated tests with pytest.
# Tests use their own temporary database, so your real data is not touched.
#
# Usage:  ./scripts/test.sh                (all tests)
#         ./scripts/test.sh -k search      (extra arguments are passed to pytest)
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT"

activate_venv

echo "==> Running tests..."
# -v: list every test by name with PASSED/FAILED. "$@" forwards any extra arguments.
python -m pytest -v "$@"
