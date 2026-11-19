from datetime import date, timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from railway.extensions import db
from railway.models import Coupling, RouteVariant, Run, Station, Stop
from railway.services.coupling import create_coupling, remove_coupling
from railway.services.stock import effective_stock
from railway.services.times import WARSAW, instant

from ..public import default_date
from . import admin


@admin.route("/laczenia", methods=["GET", "POST"])
def couplings():
    if request.method == "POST":
        try:
            create_coupling(
                *(int(request.form[k]) for k in ("source_a", "source_b", "target")),
                request.form.get("note", ""),
            )
            flash("Połączono oba składy. Dalej jadą jako jeden pociąg.", "success")
        except (ValueError, KeyError) as error:
            db.session.rollback()
            flash(str(error), "error")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Coupling failed")
            flash("Kurs został już użyty albo dane uległy zmianie. Odśwież listę.", "error")
        return redirect(
            url_for(
                "admin.couplings",
                date=request.form.get("date"),
                station=request.form.get("station"),
            )
        )
    try:
        day = date.fromisoformat(request.args.get("date", default_date().isoformat()))
    except ValueError:
        day = default_date()
    stations = db.session.scalars(select(Station).order_by(Station.name)).all()
    station_id = request.args.get("station", type=int) or next(
        (s.id for s in stations if s.name == "Warszawa Centralna"),
        stations[0].id if stations else 0,
    )
    incoming, outgoing = [], []
    for run in db.session.scalars(
        select(Run)
        .where(Run.service_date.between(day - timedelta(days=6), day + timedelta(days=1)))
        .where(Run.route_id.in_(select(Stop.route_id).where(Stop.station_id == station_id)))
        .options(
            joinedload(Run.route).selectinload(RouteVariant.stops),
            joinedload(Run.route).joinedload(RouteVariant.train),
        )
    ):
        if run.route.mode != "rail" or not run.route.stops:
            continue
        for stop, bucket, clock in [
            (run.route.stops[-1], incoming, "arrival"),
            (run.route.stops[0], outgoing, "departure"),
        ]:
            when = instant(run, getattr(stop, clock)).astimezone(WARSAW)
            # A departure shortly after midnight can use arrivals on the previous day.
            previous_evening = (
                bucket is incoming and when.date() == day - timedelta(days=1) and when.hour >= 22
            )
            if stop.station_id == station_id and (when.date() == day or previous_evening):
                bucket.append((run, when))
    incoming.sort(key=lambda pair: pair[1])
    outgoing.sort(key=lambda pair: pair[1])
    existing = db.session.scalars(select(Coupling).order_by(Coupling.id.desc()).limit(100)).all()
    return render_template(
        "admin/couplings.html",
        day=day,
        stations=stations,
        station_id=station_id,
        incoming=incoming,
        outgoing=outgoing,
        couplings=existing,
        effective_stock=effective_stock,
    )


@admin.post("/laczenia/<int:coupling_id>/usun")
def delete_coupling(coupling_id):
    try:
        remove_coupling(db.get_or_404(Coupling, coupling_id))
        flash("Usunięto łączenie; przywrócono niezależne składy.", "success")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("admin.couplings"))
