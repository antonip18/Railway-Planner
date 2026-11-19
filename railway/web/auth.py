import os
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

auth = Blueprint("auth", __name__)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@auth.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        path = Path(current_app.instance_path) / "admin-password.hash"
        stored = (
            current_app.config.get("ADMIN_PASSWORD_HASH")
            or os.getenv("ADMIN_PASSWORD_HASH")
            or (path.read_text().strip() if path.exists() else None)
        )
        if stored and check_password_hash(stored, request.form.get("password", "")):
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin.index"))
        flash("Nieprawidłowe hasło lub konto administratora nie zostało skonfigurowane.", "error")
    return render_template("login.html")


@auth.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("public.index"))
