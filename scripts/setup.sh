#!/usr/bin/env bash
# One-time project setup:
#   1. check Python   2. create venv   3. install requirements
#   4. create the database   5. add indexes   6. create a default admin account
#
# Usage:  ./scripts/setup.sh
# Change the admin login with environment variables, e.g.:
#   ADMIN_EMAIL=me@iitdh.ac.in ADMIN_PASSWORD=secret ./scripts/setup.sh

# -e: stop on the first error, -u: error on unset variables,
# -o pipefail: a pipeline fails if any command in it fails.
set -euo pipefail

source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT"

# Default admin account (override with environment variables).
ADMIN_NAME="${ADMIN_NAME:-Admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@campus.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

echo "==> [1/6] Checking for Python..."
find_python
echo "    Found: $($PYTHON --version)"

echo "==> [2/6] Creating virtual environment in ./venv ..."
if [ -d "$VENV_DIR" ]; then
    echo "    venv already exists, skipping."
else
    "$PYTHON" -m venv "$VENV_DIR"
    echo "    Created."
fi
activate_venv
# Inside the venv, "python" always points to the venv's Python (on every OS).
# We run Flask as "python -m flask" because that works even when the flask.exe
# launcher is blocked on Windows.

echo "==> [3/6] Installing requirements..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
echo "    Installed."

echo "==> [4/6] Creating the database (existing data will be wiped)..."
python -m flask --app app init-db

echo "==> [5/6] Adding indexes (sql/indexes.sql)..."
python -m flask --app app add-indexes

echo "==> [6/6] Creating default admin account..."
python -m flask --app app create-admin \
    --name "$ADMIN_NAME" --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD"

echo ""
echo "Setup complete!"
echo "  Admin login: $ADMIN_EMAIL / $ADMIN_PASSWORD"
echo "  Start the app with: ./scripts/run.sh"
