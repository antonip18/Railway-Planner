"""Small deterministic offline scenarios; every timetable and consist here is synthetic."""

from datetime import timedelta

from sqlalchemy import select

from railway.extensions import db
from railway.models import Dataset, RouteVariant, Run, Station, Stop, Train

from .coupling import create_coupling
from .stock import assign_default_stock, ensure_types


def create_demo(start):
    if db.session.scalar(select(RouteVariant.id).limit(1)):
        raise ValueError("Demo wymaga pustej bazy; istniejące dane nie zostały zmienione.")
    points = [
        ("Kraków Główny", 50.067, 19.947),
        ("Katowice", 50.257, 19.017),
        ("Częstochowa", 50.805, 19.120),
        ("Warszawa Centralna", 52.229, 21.003),
        ("Gdańsk Główny", 54.356, 18.644),
        ("Łódź Fabryczna", 51.769, 19.469),
        ("Poznań Główny", 52.402, 16.911),
    ]
    dataset = Dataset(
        fingerprint="demo:" + start.isoformat(),
        name="Rozkład demonstracyjny",
        version="1",
        start_date=start - timedelta(days=1),
        end_date=start + timedelta(days=6),
        attributions=[],
        report={
            "demo": True,
            "synthetic_fields": ["all timetable data", "train couplings", "rolling stock"],
        },
    )
    db.session.add(dataset)
    stations = []
    for index, (name, lat, lon) in enumerate(points):
        station = Station(source_key=f"demo:{index}", name=name, latitude=lat, longitude=lon)
        db.session.add(station)
        stations.append(station)
    ensure_types()
    db.session.flush()
    trains = {}

    def route(key, number, name, category, stops, stock):
        train = trains.get(number)
        if not train:
            train = Train(
                identity="demo:" + number,
                agency="DEMO",
                number=number,
                name=name,
                category=category,
            )
            db.session.add(train)
            db.session.flush()
            assign_default_stock(train, stock)
            trains[number] = train
        variant = RouteVariant(
            train_id=train.id,
            signature="demo:" + key,
            category=category,
            mode="rail",
            name=f"{stations[stops[0][0]].name} → {stations[stops[-1][0]].name}",
        )
        for i, (station, hour, minute, dwell) in enumerate(stops):
            arr = hour * 3600 + minute * 60
            variant.stops.append(
                Stop(
                    sequence=i,
                    station_id=stations[station].id,
                    arrival=arr,
                    departure=arr + dwell * 60,
                    platform="1",
                    track="1",
                )
            )
        variant.runs = [Run(service_date=start + timedelta(days=i)) for i in range(-1, 7)]
        db.session.add(variant)
        db.session.flush()
        return variant

    a = route("a", "100", "Małopolska", "IC", [(0, 8, 0, 0), (3, 11, 0, 0)], [2, 8, 6])
    b = route("b", "200", "Śląsk", "IC", [(1, 7, 45, 0), (2, 8, 40, 3), (3, 10, 50, 0)], [1, 3])
    c = route("c", "300", "Bałtyk", "IC", [(3, 11, 15, 0), (4, 14, 0, 0)], [1, 1])
    route("a-evening", "100", "Małopolska", "IC", [(0, 16, 0, 0), (3, 19, 0, 0)], [2, 8, 6])
    route("night", "400", "Nocny", "IC", [(0, 23, 0, 0), (3, 26, 0, 10), (4, 29, 0, 0)], [11, 8, 6])
    route("lodz", "500", "Łódź", "IC", [(0, 8, 10, 0), (5, 10, 0, 5), (3, 11, 20, 0)], [2, 8, 6])
    route("poznan", "600", "Wielkopolska", "IC", [(3, 11, 40, 0), (6, 14, 0, 0)], [2, 8, 6])
    db.session.commit()
    for index in range(8):
        create_coupling(
            a.runs[index].id,
            b.runs[index].id,
            c.runs[index].id,
            "Scenariusz demonstracyjny: całe składy A + B → C.",
        )
