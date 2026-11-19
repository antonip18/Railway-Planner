from collections import defaultdict
from datetime import date, datetime, time

from flask import Blueprint, abort, current_app, render_template, request
from itsdangerous import BadData, URLSafeSerializer
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from railway.extensions import db
from railway.models import Dataset, RouteVariant, Run, Station, Stop, Train, TripSource
from railway.services.connections import ConnectionPolicy
from railway.services.search import Journey, Leg, search_journeys
from railway.services.stock import carriage_view, effective_stock
from railway.services.times import WARSAW, instant

public = Blueprint("public", __name__)


def default_date():
    dataset = db.session.scalar(select(Dataset).limit(1))
    today = date.today()
    if (
        dataset
        and dataset.start_date
        and dataset.end_date
        and not dataset.start_date <= today <= dataset.end_date
    ):
        published = dataset.report.get("published_start_date")
        if published:
            try:
                return datetime.strptime(published, "%Y%m%d").date()
            except ValueError:
                pass
        return dataset.start_date
    return today


def serializer():
    return URLSafeSerializer(current_app.secret_key, salt="journey-v1")


@public.get("/")
def index():
    counts = {
        name: db.session.scalar(select(func.count()).select_from(model))
        for name, model in [("trains", Train), ("variants", RouteVariant), ("stations", Station)]
    }
    return render_template(
        "index.html",
        stations=db.session.scalars(select(Station).order_by(Station.name)).all(),
        day=default_date(),
        counts=counts,
    )


@public.get("/szukaj")
def search():
    try:
        start, end = int(request.args["start"]), int(request.args["end"])
        day = date.fromisoformat(request.args["date"])
        clock = time.fromisoformat(request.args.get("time", "00:00"))
        if clock.tzinfo:
            raise ValueError("Podaj lokalną godzinę bez strefy czasowej.")
        source, target = db.session.get(Station, start), db.session.get(Station, end)
        if not source or not target:
            raise ValueError("Wybierz istniejące stacje.")
        journeys = search_journeys(
            start,
            end,
            day,
            clock,
            int(request.args.get("transfers", 2)),
            int(request.args.get("minimum", 5)),
            request.args.get("wheelchair") == "1",
            request.args.get("bicycle") == "1",
        )
    except (KeyError, ValueError) as error:
        return render_template(
            "error.html", message=f"Niepoprawne kryteria wyszukiwania. {error}"
        ), 400
    results = [
        (
            journey,
            serializer().dumps(
                [(leg.run.id, leg.board, leg.alight, leg.connection) for leg in journey.legs]
            ),
        )
        for journey in journeys
    ]
    return render_template("results.html", results=results, source=source, target=target, day=day)


@public.get("/podroz/<token>")
def journey(token):
    try:
        values = serializer().loads(token)
        if not 1 <= len(values) <= 8:
            raise ValueError()
        legs = []
        for run_id, board, alight, connection in values:
            run = db.session.get(Run, run_id)
            if run is None or not 0 <= board < alight < len(run.route.stops):
                abort(404)
            legs.append(Leg(run, board, alight, connection))
    except (BadData, ValueError, TypeError):
        abort(404)
    # Signed URLs can outlive an admin edit; never present a removed coupling as a through ride.
    policy = ConnectionPolicy([leg.run for leg in legs])
    for previous, following in zip(legs, legs[1:]):
        connection = policy.connection(previous, following.run, following.board, 0)
        if (
            not connection
            or following.departure < previous.arrival
            or (following.connection == "stay" and connection[0] != "stay")
        ):
            return render_template(
                "error.html", message="Rozkład podróży uległ zmianie. Wyszukaj połączenie ponownie."
            ), 409
    return detail(Journey(tuple(legs), sum(leg.connection == "transfer" for leg in legs)))


@public.get("/kurs/<int:run_id>")
def run_detail(run_id):
    run = db.get_or_404(Run, run_id)
    return detail(Journey((Leg(run, 0, len(run.route.stops) - 1),), 0))


def detail(journey):
    sections = []
    for leg in journey.legs:
        stops = [
            {
                "station": stop.station,
                "arrival": instant(leg.run, stop.arrival).astimezone(WARSAW),
                "departure": instant(leg.run, stop.departure).astimezone(WARSAW),
                "platform": stop.platform,
                "track": stop.track,
            }
            for stop in leg.run.route.stops[leg.board : leg.alight + 1]
        ]
        sections.append(
            {
                "leg": leg,
                "stops": stops,
                "stock": [carriage_view(c) for c in effective_stock(leg.run)],
            }
        )
    return render_template("journey.html", journey=journey, sections=sections)


@public.get("/pociagi")
def trains():
    term = request.args.get("q", "").strip()[:100]
    statement = select(Train).order_by(Train.number, Train.id)
    if term:
        statement = statement.where(
            or_(Train.name.ilike("%" + term + "%"), Train.number.ilike("%" + term + "%"))
        )
    page = db.paginate(statement, per_page=20, max_per_page=20, error_out=False)
    variants = defaultdict(list)
    selected = list(
        db.session.scalars(
            select(RouteVariant)
            .where(RouteVariant.train_id.in_([t.id for t in page.items]))
            .order_by(RouteVariant.id)
            .options(
                joinedload(RouteVariant.train),
                joinedload(RouteVariant.stops).joinedload(Stop.station),
            )
        ).unique()
    )
    ids = [variant.id for variant in selected]
    first_runs = {}
    for run in db.session.scalars(
        select(Run).where(Run.route_id.in_(ids)).order_by(Run.service_date)
    ):
        first_runs.setdefault(run.route_id, run)
    alias_counts = dict(
        db.session.execute(
            select(TripSource.route_id, func.count())
            .where(TripSource.route_id.in_(ids))
            .group_by(TripSource.route_id)
        ).all()
    )
    for variant in selected:
        variants[variant.train_id].append(
            (variant, first_runs.get(variant.id), alias_counts.get(variant.id, 0))
        )
    return render_template("trains.html", page=page, variants=variants, query=term)


@public.get("/health")
def health():
    db.session.execute(select(1))
    return {"status": "ok"}
