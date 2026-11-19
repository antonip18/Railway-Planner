import csv
from datetime import date
from zipfile import ZipFile

import pytest
from conftest import write_table
from sqlalchemy import func, select

from railway.extensions import db
from railway.gtfs import FeedError, plan_import
from railway.gtfs.calendar import service_dates
from railway.gtfs.importer import import_plan
from railway.gtfs.normalization import seconds
from railway.gtfs.reader import FeedReader
from railway.models import Dataset, RouteVariant, Run, Station, Train, TripSource


def rows(feed, name):
    with (feed / name).open() as source:
        return list(csv.DictReader(source))


def test_public_train_identity_and_exact_schedule_deduplication(feed):
    plan = plan_import(feed)
    assert len(plan.trains) == 1
    assert len(plan.variants) == 2
    assert plan.report["identical_trip_aliases"] == 1
    assert sorted(len(v["dates"]) for v in plan.variants.values()) == [1, 2]
    assert {s["trip_id"] for s in plan.sources} == {"train_1", "train_2", "train_3"}
    assert "001" in plan.stations and "1" in plan.stations
    assert plan.trains["IC:123"]["name"] == "TEST"
    assert plan.report["couplings_inferred_from_suffixes"] == 0


def test_zip_and_directory_produce_identical_plan(feed, tmp_path):
    target = tmp_path / "feed.zip"
    with ZipFile(target, "w") as archive:
        for path in sorted(feed.iterdir()):
            archive.write(path, "nested/" + path.name)
    assert plan_import(target).report == plan_import(feed).report


def test_calendar_exceptions_are_not_replaced_by_weekly_guess(feed):
    write_table(
        feed,
        "calendar.txt",
        [
            {
                "service_id": "S1",
                "start_date": "20260105",
                "end_date": "20260111",
                **{
                    d: "1"
                    for d in (
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    )
                },
            }
        ],
    )
    write_table(
        feed,
        "calendar_dates.txt",
        [
            {"service_id": "S1", "date": "20260106", "exception_type": "2"},
            {"service_id": "S1", "date": "20260112", "exception_type": "1"},
            {"service_id": "S2", "date": "20260111", "exception_type": "1"},
        ],
    )
    with FeedReader(feed) as reader:
        dates = service_dates(reader)
    assert date(2026, 1, 6) not in dates["S1"]
    assert date(2026, 1, 12) in dates["S1"]
    assert date(2026, 1, 13) not in dates["S1"]
    assert len(dates["S1"]) == 7


@pytest.mark.parametrize(
    "value,expected", [("00:00:00", 0), ("24:30:15", 88215), ("49:00:00", 176400)]
)
def test_gtfs_seconds_preserve_days_and_seconds(value, expected):
    assert seconds(value) == expected


@pytest.mark.parametrize("value", ["12:60:00", "24:00:60", "-1:00:00", "168:00:00", ""])
def test_invalid_times_are_rejected(value):
    with pytest.raises(FeedError):
        seconds(value)


def test_import_is_atomic_and_idempotent(app, feed):
    plan = plan_import(feed)
    dataset, created = import_plan(plan)
    assert created
    assert not import_plan(plan)[1]
    assert db.session.scalar(select(func.count()).select_from(Train)) == 1
    assert db.session.scalar(select(func.count()).select_from(RouteVariant)) == 2
    assert db.session.scalar(select(func.count()).select_from(Run)) == 3
    assert db.session.scalar(select(func.count()).select_from(TripSource)) == 3
    variant = db.session.scalar(select(RouteVariant))
    assert all(s.platform is None and s.track is None for s in variant.stops)
    assert [
        s.source_key for s in db.session.scalars(select(Station).order_by(Station.source_key))
    ] == ["001", "1", "Z"]
    assert dataset.report["source_trips"] == 3
    # A different feed is not silently overlaid on the old timetable.
    new_rows = rows(feed, "stop_times.txt")
    new_rows[0]["platform"] = "2"
    write_table(feed, "stop_times.txt", new_rows)
    with pytest.raises(FeedError):
        import_plan(plan_import(feed))
    assert db.session.scalar(select(func.count()).select_from(Dataset)) == 1


def test_replacement_bus_legs_are_not_spliced_into_a_fake_train(feed):
    route_rows = rows(feed, "routes.txt")
    route_rows.append({**route_rows[0], "route_id": "IC_BUS", "route_type": "3"})
    write_table(feed, "routes.txt", route_rows)
    trips = rows(feed, "trips.txt")
    trips[0]["trip_id"] = "PLK_X_LEG0"
    trips[1]["trip_id"] = "PLK_X_LEG1"
    trips[1]["route_id"] = "IC_BUS"
    write_table(feed, "trips.txt", trips)
    stop_rows = rows(feed, "stop_times.txt")
    for r in stop_rows:
        r["trip_id"] = {"train_1": "PLK_X_LEG0", "train_2": "PLK_X_LEG1"}.get(
            r["trip_id"], r["trip_id"]
        )
    write_table(feed, "stop_times.txt", stop_rows)
    write_table(
        feed,
        "transfers.txt",
        [
            {
                "from_stop_id": "Z",
                "to_stop_id": "001",
                "from_trip_id": "PLK_X_LEG0",
                "to_trip_id": "PLK_X_LEG1",
                "transfer_type": "1",
            }
        ],
    )
    plan = plan_import(feed)
    assert len(plan.variants) == 3 and len(plan.trains) == 1
    assert plan.report["replacement_bus_variants"] == 1
    assert plan.report["transfer_types"] == {"1": 1}


def test_invalid_trip_is_reported_without_partially_importing_it(feed):
    stop_rows = rows(feed, "stop_times.txt")
    stop_rows[0]["arrival_time"] = "bad"
    write_table(feed, "stop_times.txt", stop_rows)
    with pytest.raises(FeedError):
        plan_import(feed)
    plan = plan_import(feed, strict=False)
    assert len(plan.report["rejected_trips"]) == 1
    assert "train_1" not in {s["trip_id"] for s in plan.sources}


def test_repeated_station_visits_are_kept_in_sequence(feed):
    stop_rows = rows(feed, "stop_times.txt")
    for r in stop_rows:
        if r["stop_sequence"] == "2":
            r["stop_id"] = "001"
    write_table(feed, "stop_times.txt", stop_rows)
    assert all(
        [s["station_key"] for s in v["stops"]] == ["001", "1", "001"]
        for v in plan_import(feed).variants.values()
    )


def test_parent_station_coordinates_are_canonical(feed):
    import csv

    from conftest import write_table

    from railway.gtfs.normalization import station_records
    from railway.gtfs.reader import FeedReader

    rows = list(csv.DictReader((feed / "stops.txt").open()))
    rows[0]["parent_station"] = "1"
    write_table(feed, "stops.txt", rows)
    with FeedReader(feed) as reader:
        stations = station_records(reader)
    assert stations["001"]["key"] == "1"
    assert stations["001"]["latitude"] == stations["1"]["latitude"] == 51


def test_duplicate_stop_ids_are_not_silently_overwritten(feed):
    import csv

    from conftest import write_table

    rows = list(csv.DictReader((feed / "stops.txt").open()))
    write_table(feed, "stops.txt", rows + [rows[0]])
    with pytest.raises(ValueError, match="duplicate stop_id"):
        plan_import(feed)


def test_unsupported_timezone_is_rejected(feed):
    table = feed / "agency.txt"
    table.write_text(table.read_text().replace("Europe/Warsaw", "America/New_York"))
    with pytest.raises(ValueError, match="Europe/Warsaw"):
        plan_import(feed)


def test_frequency_feed_is_not_misrepresented_as_one_scheduled_trip(feed):
    (feed / "frequencies.txt").write_text(
        "trip_id,start_time,end_time,headway_secs\ntrain_1,08:00:00,09:00:00,600\n"
    )
    with pytest.raises(ValueError, match="Frequency-based"):
        plan_import(feed)
