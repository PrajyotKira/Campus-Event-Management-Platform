"""Admin-only pages. Phase 2 has only a placeholder dashboard, so the
admin_required decorator can be used and tested. Event/venue CRUD, CSV export
and reports come in phase 3."""
from flask import Blueprint, render_template

from .auth import admin_required

# All routes in this file start with /admin
bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html")
