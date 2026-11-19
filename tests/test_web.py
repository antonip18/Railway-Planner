from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from railway.services.carriage_catalog import TYPY_WAGONOW


def test_public_pages_and_journey_links(demo, client):
    for url in [
        "/",
        "/pociagi",
        "/health",
        "/szukaj?start=1&end=5&date=2026-01-10&time=07:00&transfers=0",
    ]:
        response = client.get(url)
        assert response.status_code == 200, url
    result = client.get("/szukaj?start=1&end=5&date=2026-01-10&time=07:00&transfers=0").get_data(
        as_text=True
    )
    import re

    urls = re.findall(r'href="(/podroz/[^"]+)"', result)
    assert urls
    page = client.get(urls[0])
    assert page.status_code == 200
    assert "Wszystkie jego wagony" in page.get_data(as_text=True)
    assert client.get("/podroz/modified-token").status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        "",
        "start=1&end=5&date=no",
        "start=abc&end=5&date=2026-01-10",
        "start=1&end=1&date=2026-01-10",
        "start=1&end=5&date=2026-01-10&transfers=9",
    ],
)
def test_search_validation_returns_400(demo, client, query):
    assert client.get("/szukaj?" + query).status_code == 400


def test_admin_requires_login_and_csrf(demo, client):
    assert client.get("/admin").status_code == 302
    demo.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/admin/trasy/nowa", data={}).status_code == 400
    demo.config["WTF_CSRF_ENABLED"] = False
    demo.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("a-long-test-password")
    assert client.post("/admin/login", data={"password": "wrong"}).status_code == 200
    assert client.post("/admin/login", data={"password": "a-long-test-password"}).status_code == 302
    assert client.get("/admin").status_code == 200
    client.post("/admin/logout")
    assert client.get("/admin").status_code == 302


def test_admin_pages_render(demo, client):
    with client.session_transaction() as session:
        session["admin"] = True
    for url in [
        "/admin",
        "/admin/trasy",
        "/admin/trasy/nowa",
        "/admin/laczenia?date=2026-01-10&station=4",
        "/admin/tabor",
    ]:
        assert client.get(url).status_code == 200, url


@pytest.mark.parametrize("definition", TYPY_WAGONOW, ids=lambda d: str(d.id_typu))
def test_existing_carriage_layouts_have_valid_unique_seats(definition):
    elements, seats = definition.builder()
    assert len({(s.rzad, s.kolumna) for s in seats}) == len(seats)
    assert len({s.numer for s in seats}) == len(seats)
    for seat in seats:
        assert 1 <= seat.rzad <= definition.liczba_rzedow
        assert 1 <= seat.kolumna <= definition.liczba_kolumn
    for element in elements:
        assert 1 <= element.rzad_od <= element.rzad_do <= definition.liczba_rzedow
        assert 1 <= element.kolumna_od <= element.kolumna_do <= definition.liczba_kolumn


def test_invalid_route_preserves_all_submitted_rows(demo, client):
    with client.session_transaction() as session:
        session["admin"] = True
    response = client.post(
        "/admin/trasy/nowa",
        data={
            "number": "EDIT",
            "name": "Preserved",
            "category": "IC",
            "dates": "2026-01-10",
            "station_id": ["1", "4", "5"],
            "arrival": ["23:00", "wrong", "26:15"],
            "departure": ["23:05", "25:15", "26:20"],
            "platform": ["9", "10", "11"],
            "track": ["3", "4", "5"],
            "carriage_type": ["2", "8"],
        },
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('name="station_id"') == 3
    assert html.count('name="carriage_type"') == 2
    assert 'value="wrong"' in html and 'value="26:15"' in html


def test_saved_journey_does_not_claim_a_removed_coupling(demo, client):
    import re

    from sqlalchemy import select

    from railway.extensions import db
    from railway.models import Coupling, RouteVariant, Run
    from railway.services.coupling import remove_coupling

    result = client.get("/szukaj?start=1&end=5&date=2026-01-10&time=07:00&transfers=0").get_data(
        as_text=True
    )
    url = re.findall(r'href="(/podroz/[^\"]+)"', result)[0]
    assert client.get(url).status_code == 200
    output = db.session.scalar(
        select(Run)
        .join(RouteVariant)
        .where(
            RouteVariant.signature == "demo:c",
            Run.service_date == date(2026, 1, 10),
        )
    )
    remove_coupling(db.session.scalar(select(Coupling).where(Coupling.output_run_id == output.id)))
    assert client.get(url).status_code == 409
