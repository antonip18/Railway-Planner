from datetime import date, time, timedelta

import pytest
from sqlalchemy import func, select

from railway.extensions import db
from railway.models import Coupling, RouteVariant, Run, Station
from railway.services.coupling import create_coupling, remove_coupling
from railway.services.search import search_journeys
from railway.services.stock import effective_stock
from railway.services.times import WARSAW, instant

DAY = date(2026, 1, 10)


def run(key, day=DAY):
    return db.session.scalar(
        select(Run)
        .join(RouteVariant)
        .where(RouteVariant.signature == "demo:" + key, Run.service_date == day)
    )


def station(name):
    return db.session.scalar(select(Station.id).where(Station.name == name))


def find(start="Kraków Główny", end="Gdańsk Główny", clock=time(7), transfers=0, day=DAY):
    return search_journeys(station(start), station(end), day, clock, max_transfers=transfers)


def test_coupling_combines_all_carriages_in_order_and_only_for_one_run(demo):
    a, b, c = run("a"), run("b"), run("c")
    expected = [w.id for w in a.route.train.carriages] + [w.id for w in b.route.train.carriages]
    assert [w.id for w in effective_stock(c)] == expected
    assert len(expected) == 5
    coupling = db.session.scalar(select(Coupling).where(Coupling.output_run_id == c.id))
    remove_coupling(coupling)
    assert [w.id for w in effective_stock(c)] == [w.id for w in c.route.train.carriages]
    assert len(effective_stock(run("c", DAY + timedelta(days=1)))) == 5
    assert len(effective_stock(a)) == 3 and len(effective_stock(b)) == 2


def test_joined_trains_are_a_zero_transfer_journey(demo):
    results = find()
    joined = next(
        j for j in results if [leg.run.id for leg in j.legs] == [run("a").id, run("c").id]
    )
    assert joined.transfers == 0 and joined.legs[1].connection == "stay"
    assert joined.minutes == 360
    assert next(j for j in find("Katowice") if len(j.legs) == 2).transfers == 0


def test_without_coupling_continuation_requires_a_real_transfer(demo):
    c = run("c")
    remove_coupling(db.session.scalar(select(Coupling).where(Coupling.output_run_id == c.id)))
    assert not any(len(j.legs) == 2 for j in find())
    assert any(len(j.legs) == 2 and j.transfers == 1 for j in find(transfers=1))


def test_previous_service_day_is_used_after_midnight(demo):
    results = find("Warszawa Centralna", clock=time(1), day=DAY)
    night = next(j for j in results if j.legs[0].run.route.signature == "demo:night")
    assert night.legs[0].run.service_date == DAY - timedelta(days=1)
    assert night.legs[0].local_departure.date() == DAY
    assert night.legs[0].local_departure.hour == 2
    assert night.legs[-1].local_arrival.hour == 5


def test_calendar_has_finite_bounds(demo):
    assert not find(day=date(2027, 1, 10))


def test_failed_coupling_does_not_change_any_consist(demo):
    before = db.session.scalar(select(func.count()).select_from(Coupling))
    with pytest.raises(ValueError):
        create_coupling(run("a").id, run("a").id, run("c").id)
    with pytest.raises(ValueError):
        create_coupling(run("a").id, run("b").id, run("c").id)
    assert db.session.scalar(select(func.count()).select_from(Coupling)) == before
    assert len(effective_stock(run("c"))) == 5


def test_rejects_impossible_station_or_time(demo):
    target = run("c")
    remove_coupling(db.session.scalar(select(Coupling).where(Coupling.output_run_id == target.id)))
    with pytest.raises(ValueError, match="5 do 120"):
        create_coupling(run("a-evening").id, run("b").id, target.id)
    with pytest.raises(ValueError, match="kończyć trasę"):
        create_coupling(run("a").id, run("poznan").id, target.id)
    assert len(effective_stock(target)) == 2


def test_coupling_is_reversible_and_reusable(demo):
    target = run("c")
    remove_coupling(db.session.scalar(select(Coupling).where(Coupling.output_run_id == target.id)))
    create_coupling(run("b").id, run("a").id, target.id)
    assert effective_stock(target)[0].train.number == "200"
    assert effective_stock(target)[-1].train.number == "100"


def test_no_boarding_at_a_non_pickup_stop(demo):
    run("night", DAY - timedelta(days=1)).route.stops[1].pickup = False
    db.session.commit()
    assert not any(
        j.legs[0].run.route.signature == "demo:night"
        for j in find("Warszawa Centralna", clock=time(1))
    )


def test_gtfs_day_anchor_handles_dst():
    class Service:
        service_date = date(2026, 3, 29)

    assert instant(Service(), 3 * 3600).astimezone(WARSAW).hour == 3
    assert (instant(Service(), 4 * 3600) - instant(Service(), 3 * 3600)).total_seconds() == 3600


def test_coupling_can_cross_calendar_midnight_and_keeps_both_service_dates(demo, client):
    from railway.services.stock import add_carriage

    a, b, c = run("a"), run("b"), run("c", DAY + timedelta(days=1))
    for coupling in db.session.scalars(select(Coupling)).all():
        remove_coupling(coupling)
    a.route.stops[-1].arrival = a.route.stops[-1].departure = 23 * 3600 + 50 * 60
    b.route.stops[-1].arrival = b.route.stops[-1].departure = 23 * 3600 + 45 * 60
    c.route.stops[0].arrival = c.route.stops[0].departure = 10 * 60
    c.route.stops[-1].arrival = c.route.stops[-1].departure = 3 * 3600
    db.session.commit()
    with client.session_transaction() as session:
        session["admin"] = True
    html = client.get("/admin/laczenia?date=2026-01-11&station=4").get_data(as_text=True)
    assert "10.01 23:50" in html and "11.01 00:10" in html
    create_coupling(a.id, b.id, c.id)
    assert len(effective_stock(c)) == 5
    with pytest.raises(ValueError, match="usuń łączenia"):
        add_carriage(a.route.train_id, 1)
    results = find(clock=time(7))
    assert any([leg.run.id for leg in j.legs] == [a.id, c.id] and j.transfers == 0 for j in results)
