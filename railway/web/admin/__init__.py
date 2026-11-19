from flask import Blueprint, render_template
from sqlalchemy import func, select

from railway.extensions import db
from railway.models import Carriage, Coupling, RouteVariant, Train

from ..auth import admin_required

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.before_request
@admin_required
def require_admin():
    return None


@admin.get("")
def index():
    counts = {
        key: db.session.scalar(select(func.count()).select_from(model))
        for key, model in [
            ("trains", Train),
            ("routes", RouteVariant),
            ("couplings", Coupling),
            ("carriages", Carriage),
        ]
    }
    return render_template("admin/index.html", counts=counts)


from . import couplings, routes, stock  # noqa: E402,F401
