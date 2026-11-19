import csv
from datetime import date

import pytest

from railway import create_app
from railway.extensions import db
from railway.services.demo import create_demo


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db"),
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def demo(app):
    create_demo(date(2026, 1, 10))
    return app


def write_table(path, name, rows):
    with (path / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def feed(tmp_path):
    path = tmp_path / "gtfs"
    path.mkdir()
    write_table(
        path,
        "agency.txt",
        [{"agency_id": "IC", "agency_name": "Fixture", "agency_timezone": "Europe/Warsaw"}],
    )
    write_table(
        path,
        "routes.txt",
        [{"route_id": "IC_R", "agency_id": "IC", "route_type": "2", "route_short_name": "IC"}],
    )
    write_table(
        path,
        "stops.txt",
        [
            {
                "stop_id": "001",
                "stop_name": "Alpha",
                "stop_lat": "50",
                "stop_lon": "19",
                "parent_station": "",
                "location_type": "0",
            },
            {
                "stop_id": "1",
                "stop_name": "Beta",
                "stop_lat": "51",
                "stop_lon": "20",
                "parent_station": "",
                "location_type": "0",
            },
            {
                "stop_id": "Z",
                "stop_name": "Gamma",
                "stop_lat": "52",
                "stop_lon": "21",
                "parent_station": "",
                "location_type": "0",
            },
        ],
    )
    trips = [
        {
            "trip_id": key,
            "route_id": "IC_R",
            "service_id": service,
            "trip_short_name": "123",
            "plk_train_number": "123",
            "plk_train_name": "TEST",
            "plk_category_code": "IC",
            "block_id": "same-block",
        }
        for key, service in [("train_1", "S1"), ("train_2", "S2"), ("train_3", "S1")]
    ]
    write_table(path, "trips.txt", trips)
    times = []
    for trip in trips:
        hour = 8 if trip["trip_id"] != "train_3" else 9
        for seq, stop in enumerate(("001", "1", "Z")):
            times.append(
                {
                    "trip_id": trip["trip_id"],
                    "stop_sequence": str(seq),
                    "stop_id": stop,
                    "arrival_time": f"{hour + seq:02}:00:00",
                    "departure_time": f"{hour + seq:02}:00:00",
                    "platform": "",
                    "track": "",
                    "pickup_type": "0",
                    "drop_off_type": "0",
                }
            )
    write_table(path, "stop_times.txt", times)
    write_table(
        path,
        "calendar_dates.txt",
        [
            {"service_id": s, "date": day, "exception_type": "1"}
            for s, day in [("S1", "20260110"), ("S2", "20260111")]
        ],
    )
    return path
