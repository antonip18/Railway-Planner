"""Optional integration tests, run against a dedicated disposable PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from railway import create_app
from railway.cli import migration_config
from railway.extensions import db
from railway.gtfs import plan_import
from railway.gtfs.importer import import_plan
from railway.models import Coupling, CouplingInput, RouteVariant, Run
from railway.services.coupling import create_coupling, remove_coupling
from railway.services.demo import create_demo
from railway.services.routes import save_route
from railway.services.stock import effective_stock

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a disposable PostgreSQL database.",
)


@pytest.fixture
def pg_app():
    uri = os.environ["TEST_DATABASE_URL"]
    if not make_url(uri).database.startswith("railway_test"):
        pytest.fail("Integration database name must start with railway_test.")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "WTF_CSRF_ENABLED": False})
    with app.app_context():
        # This schema belongs exclusively to the explicitly selected test database.
        with db.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield app
        db.session.remove()


def test_postgres_migration_matches_models_and_can_be_reversed(pg_app):
    with db.engine.begin() as connection:
        assert compare_metadata(MigrationContext.configure(connection), db.metadata) == []
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        assert compare_metadata(MigrationContext.configure(connection), db.metadata) == []


def test_postgres_import_is_idempotent(pg_app, feed):
    plan = plan_import(feed)
    assert import_plan(plan)[1]
    assert not import_plan(plan)[1]
    assert len(db.session.scalars(select(Run)).all()) == 3


def test_concurrent_couplings_cannot_consume_the_same_input(pg_app):
    day = date(2026, 1, 10)
    create_demo(day)

    def find(key):
        return db.session.scalar(
            select(Run)
            .join(RouteVariant)
            .where(RouteVariant.signature == "demo:" + key, Run.service_date == day)
        )

    a, b, c = find("a"), find("b"), find("c")
    remove_coupling(db.session.scalar(select(Coupling).where(Coupling.output_run_id == c.id)))
    alternative = save_route(
        {
            "number": "ALT",
            "name": "Alternative",
            "category": "IC",
            "types": [1],
            "dates": [day],
            "stops": [
                {
                    "sequence": i,
                    "station_id": s.station_id,
                    "arrival": s.arrival,
                    "departure": s.departure,
                    "platform": None,
                    "track": None,
                }
                for i, s in enumerate(c.route.stops)
            ],
        }
    )
    input_a, input_b = a.id, b.id
    targets = [c.id, alternative.runs[0].id]
    barrier = Barrier(2)

    def attempt(target):
        with pg_app.app_context():
            barrier.wait(timeout=10)
            try:
                create_coupling(input_a, input_b, target)
                return True
            except ValueError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, targets))
    assert sorted(outcomes) == [False, True]
    db.session.expire_all()
    assert (
        len(db.session.scalars(select(CouplingInput).where(CouplingInput.run_id == input_a)).all())
        == 1
    )
    assert sorted(len(effective_stock(db.session.get(Run, target))) for target in targets) == [
        1,
        5,
    ] or sorted(len(effective_stock(db.session.get(Run, target))) for target in targets) == [2, 5]


@pytest.mark.skipif(
    not os.getenv("REAL_GTFS_PATH"),
    reason="Set REAL_GTFS_PATH for the source-feed integration check.",
)
def test_full_source_feed_import_and_search(pg_app):
    from datetime import time

    from railway.models import Station
    from railway.services.search import search_journeys

    plan = plan_import(os.environ["REAL_GTFS_PATH"])
    dataset, created = import_plan(plan)
    assert created
    assert plan.report["source_trips"] == 3732
    assert plan.report["schedule_variants"] == 1221
    assert plan.report["dated_runs"] == 18833

    def station(name):
        return db.session.scalar(select(Station.id).where(Station.name == name))

    results = search_journeys(
        station("Kraków Główny"),
        station("Warszawa Centralna"),
        date(2026, 5, 12),
        time(7),
        max_transfers=1,
    )
    assert results
    assert all(j.legs[-1].arrival >= j.legs[0].departure for j in results)
