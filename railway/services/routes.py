"""Validation and atomic editing of manually created timetable variants."""

from datetime import date
from uuid import uuid4

from sqlalchemy import select

from railway.extensions import db
from railway.models import RouteVariant, Run, Station, Stop, Train

from .coupling import lock_route_runs, route_is_coupled
from .stock import assign_default_stock, ensure_types
from .times import parse_input_time


def parse_route_form(form):
    station_ids, arrivals, departures = (
        form.getlist(k) for k in ("station_id", "arrival", "departure")
    )
    if (
        len(station_ids) < 2
        or len(station_ids) > 100
        or len({len(station_ids), len(arrivals), len(departures)}) != 1
    ):
        raise ValueError("Trasa wymaga od 2 do 100 kompletnych postojów.")
    known = set(db.session.scalars(select(Station.id)))
    stops = []
    last = -1
    platforms, tracks = form.getlist("platform"), form.getlist("track")
    for index, (station, arrival, departure) in enumerate(
        zip(station_ids, arrivals, departures, strict=True)
    ):
        if int(station) not in known:
            raise ValueError("Nieznana stacja.")
        arr, dep = parse_input_time(arrival), parse_input_time(departure)
        if arr < last or dep < arr:
            raise ValueError("Godziny muszą być chronologiczne; po północy wpisz np. 24:30.")
        last = dep
        stops.append(
            {
                "sequence": index,
                "station_id": int(station),
                "arrival": arr,
                "departure": dep,
                "platform": (platforms[index].strip() or None) if index < len(platforms) else None,
                "track": (tracks[index].strip() or None) if index < len(tracks) else None,
            }
        )
    dates = sorted(
        {
            date.fromisoformat(value.strip())
            for value in form.get("dates", "").split(",")
            if value.strip()
        }
    )
    if not dates or len(dates) > 366:
        raise ValueError("Podaj od 1 do 366 dat kursowania (RRRR-MM-DD), oddzielonych przecinkami.")
    number, name, category = (form.get(k, "").strip() for k in ("number", "name", "category"))
    if not number or not category or len(number) > 100 or len(name) > 200 or len(category) > 40:
        raise ValueError("Uzupełnij numer i kategorię pociągu; nazwa może mieć do 200 znaków.")
    types = [int(value) for value in form.getlist("carriage_type") if value]
    if not 1 <= len(types) <= 30:
        raise ValueError("Skład powinien zawierać od 1 do 30 wagonów.")
    return {
        "stops": stops,
        "dates": dates,
        "number": number,
        "name": name,
        "category": category,
        "types": types,
    }


def save_route(data, route=None):
    try:
        if route:
            lock_route_runs([route.id])
        if route and (route.dataset_id or route_is_coupled(route.id)):
            raise ValueError(
                "Nie można edytować zaimportowanej trasy ani trasy uczestniczącej w łączeniu."
            )
        ensure_types()
        if route is None:
            train = Train(
                identity="manual:" + uuid4().hex,
                agency="DEMO",
                number=data["number"],
                name=data["name"],
                category=data["category"],
            )
            db.session.add(train)
            db.session.flush()
            route = RouteVariant(
                train_id=train.id,
                signature=uuid4().hex,
                mode="rail",
                name="",
                category=train.category,
            )
            db.session.add(route)
        else:
            train = route.train
            if db.session.scalar(
                select(RouteVariant.id).where(
                    RouteVariant.train_id == train.id, RouteVariant.id != route.id
                )
            ):
                raise ValueError(
                    "Ten pociąg ma wiele wariantów; utwórz nową trasę zamiast zmieniać wspólny skład."
                )
            train.carriages.clear()
            route.stops.clear()
            route.runs.clear()
            db.session.flush()
            train.number = data["number"]
            train.name = data["name"]
            train.category = data["category"]
            route.category = data["category"]
        assign_default_stock(train, data["types"])
        route.stops = [Stop(**stop) for stop in data["stops"]]
        route.runs = [Run(service_date=day) for day in data["dates"]]
        names = [db.session.get(Station, data["stops"][i]["station_id"]).name for i in (0, -1)]
        route.name = " → ".join(names)
        db.session.commit()
        return route
    except Exception:
        db.session.rollback()
        raise


def delete_route(route):
    lock_route_runs([route.id])
    if route.dataset_id or route_is_coupled(route.id):
        raise ValueError(
            "Nie można usunąć zaimportowanej trasy ani trasy biorącej udział w łączeniu."
        )
    train = route.train
    db.session.delete(route)
    db.session.flush()
    if not db.session.scalar(select(RouteVariant.id).where(RouteVariant.train_id == train.id)):
        db.session.delete(train)
    db.session.commit()
