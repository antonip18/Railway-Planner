from flask import current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from railway.extensions import db
from railway.models import CarriageType, Train
from railway.services.stock import add_carriage

from . import admin


@admin.route("/tabor", methods=["GET", "POST"])
def stock():
    if request.method == "POST":
        try:
            add_carriage(
                request.form.get("train_id", type=int), request.form.get("type_id", type=int)
            )
            flash("Dodano wagon do bazowego składu demonstracyjnego.", "success")
        except ValueError as error:
            flash(str(error), "error")
        except SQLAlchemyError:
            current_app.logger.exception("Stock update failed")
            flash("Nie udało się zmienić składu. Odśwież stronę i spróbuj ponownie.", "error")
        return redirect(url_for("admin.stock"))
    page = db.paginate(select(Train).order_by(Train.id), per_page=20, error_out=False)
    return render_template(
        "admin/stock.html",
        page=page,
        types=db.session.scalars(select(CarriageType).order_by(CarriageType.id)).all(),
    )
