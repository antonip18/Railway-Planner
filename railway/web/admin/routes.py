from flask import current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from railway.extensions import db
from railway.models import CarriageType, RouteVariant, Station
from railway.services.routes import delete_route, parse_route_form, save_route
from railway.services.stock import ensure_types

from . import admin


def form_values(route):
    """Keep every submitted row after validation errors, including invalid time text."""
    if request.method == "POST":
        fields = ("station_id", "arrival", "departure", "platform", "track")
        columns = {key: request.form.getlist(key) for key in fields}
        rows = [
            {key: values[i] if i < len(values) else "" for key, values in columns.items()}
            for i in range(min(100, max(2, len(columns["station_id"]))))
        ]
        return rows, request.form.getlist("carriage_type")[:30] or [""]
    if route:

        def clock(value):
            return f"{value // 3600:02}:{value % 3600 // 60:02}:{value % 60:02}"

        rows = [
            dict(
                station_id=s.station_id,
                arrival=clock(s.arrival),
                departure=clock(s.departure),
                platform=s.platform,
                track=s.track,
            )
            for s in route.stops
        ]
        return rows, [car.type_id for car in route.train.carriages]
    return [
        dict(station_id="", arrival="", departure="", platform="", track="") for _ in range(2)
    ], [""]


@admin.get("/trasy")
def routes():
    page = db.paginate(
        select(RouteVariant).order_by(RouteVariant.id.desc()), per_page=30, error_out=False
    )
    return render_template("admin/routes.html", page=page)


@admin.route("/trasy/nowa", methods=["GET", "POST"])
@admin.route("/trasy/<int:route_id>/edytuj", methods=["GET", "POST"])
def edit_route(route_id=None):
    route = db.get_or_404(RouteVariant, route_id) if route_id else None
    if route and route.dataset_id:
        flash(
            "Warianty GTFS są tylko do odczytu. Utwórz własną trasę, aby zaplanować scenariusz.",
            "error",
        )
        return redirect(url_for("admin.routes"))
    if request.method == "POST":
        try:
            save_route(parse_route_form(request.form), route)
            flash("Zapisano trasę i dokładne daty kursowania.", "success")
            return redirect(url_for("admin.routes"))
        except (ValueError, KeyError) as error:
            db.session.rollback()
            flash(str(error), "error")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Route update failed")
            flash("Nie udało się zapisać trasy. Dane nie zostały zmienione.", "error")
    ensure_types()
    db.session.commit()
    form_stops, form_cars = form_values(route)
    return render_template(
        "admin/edit_route.html",
        route=route,
        stations=db.session.scalars(select(Station).order_by(Station.name)).all(),
        types=db.session.scalars(select(CarriageType).order_by(CarriageType.id)).all(),
        form_stops=form_stops,
        form_cars=form_cars,
    )


@admin.post("/trasy/<int:route_id>/usun")
def remove_route(route_id):
    try:
        delete_route(db.get_or_404(RouteVariant, route_id))
        flash("Usunięto trasę.", "success")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "error")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Route deletion failed")
        flash("Trasa ma powiązane dane i nie może zostać usunięta.", "error")
    return redirect(url_for("admin.routes"))
