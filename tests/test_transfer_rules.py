from datetime import time

import pytest
from sqlalchemy import select
from test_couplings_and_search import DAY, run, station

from railway.extensions import db
from railway.models import Coupling, Dataset, TransferRule, TripSource
from railway.services.coupling import remove_coupling
from railway.services.search import search_journeys


def setup_rule(kind, minimum=None):
    a, c = run("a"), run("c")
    remove_coupling(db.session.scalar(select(Coupling).where(Coupling.output_run_id == c.id)))
    dataset = db.session.scalar(select(Dataset))
    for name, trip in [("A", a), ("C", c)]:
        trip.route.dataset_id = dataset.id
        db.session.add(
            TripSource(
                dataset_id=dataset.id,
                trip_id=name,
                route_id=trip.route_id,
                gtfs_route_id="IC",
                service_id="D",
                block_id="same",
                dates=[DAY.isoformat()],
            )
        )
    db.session.add(
        TransferRule(
            dataset_id=dataset.id,
            from_station_id=station("Warszawa Centralna"),
            to_station_id=station("Warszawa Centralna"),
            from_trip_id="A",
            to_trip_id="C",
            transfer_type=kind,
            minimum_seconds=minimum,
        )
    )
    db.session.commit()
    return a.id, c.id


@pytest.mark.parametrize(
    "kind,transfers,expected",
    [(1, 0, False), (1, 1, True), (4, 0, True), (5, 0, False), (5, 1, True), (3, 2, False)],
)
def test_only_explicit_in_seat_transfer_allows_staying_onboard(demo, kind, transfers, expected):
    ids = setup_rule(kind)
    results = search_journeys(
        station("Kraków Główny"), station("Gdańsk Główny"), DAY, time(7), max_transfers=transfers
    )
    assert any(tuple(leg.run.id for leg in journey.legs) == ids for journey in results) == expected


def test_minimum_transfer_time_is_respected(demo):
    ids = setup_rule(2, 30 * 60)
    results = search_journeys(
        station("Kraków Główny"), station("Gdańsk Główny"), DAY, time(7), max_transfers=1
    )
    assert not any(tuple(leg.run.id for leg in journey.legs) == ids for journey in results)
