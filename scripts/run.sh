#!/usr/bin/env bash
# Start the Flask development server.
# Usage:  ./scripts/run.sh            (http://127.0.0.1:5000)
#         PORT=8000 ./scripts/run.sh  (use a different port)
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT"

PORT="${PORT:-5000}"

activate_venv

# The database is created by setup.sh; stop with a helpful message if it is missing.
if [ ! -f "instance/campus.db" ]; then
    echo "ERROR: database not found. Run ./scripts/setup.sh first."
    exit 1
fi

echo "==> Starting server at http://127.0.0.1:$PORT  (press Ctrl+C to stop)"
# --debug: auto-reload when code changes and show detailed error pages.
python -m flask --app app run --debug --port "$PORT"
