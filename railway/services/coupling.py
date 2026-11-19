from sqlalchemy import or_, select

from railway.extensions import db
from railway.models import Coupling, CouplingInput, Run

from .stock import effective_stock
from .times import instant

MINIMUM_DWELL = 5 * 60
MAXIMUM_DWELL = 120 * 60


def create_coupling(source_a, source_b, target, note=""):
    """Validate and commit A + B → C atomically; composition itself is derived, never moved."""
    ids = [source_a, source_b, target]
    if len(set(ids)) != 3:
        raise ValueError("Wybierz trzy różne kursy: dwa przyjeżdżające i jeden odjeżdżający.")
    try:
        # Ordered row locks serialize competing operations on PostgreSQL.
        runs = {
            run.id: run
            for run in db.session.scalars(
                select(Run).where(Run.id.in_(ids)).order_by(Run.id).with_for_update()
            )
        }
        if len(runs) != 3:
            raise ValueError("Wybrany kurs nie istnieje.")
        a, b, c = (runs[i] for i in ids)
        if any(run.route.mode != "rail" or len(run.route.stops) < 2 for run in (a, b, c)):
            raise ValueError("Można łączyć wyłącznie pociągi z co najmniej dwoma postojami.")
        if db.session.scalar(select(CouplingInput).where(CouplingInput.run_id.in_([a.id, b.id]))):
            raise ValueError("Jeden z pociągów już bierze udział w innym łączeniu.")
        if db.session.scalar(select(Coupling).where(Coupling.output_run_id == c.id)):
            raise ValueError("Pociąg wynikowy ma już przypisane łączenie.")
        station_id = c.route.stops[0].station_id
        if a.route.stops[-1].station_id != station_id or b.route.stops[-1].station_id != station_id:
            raise ValueError(
                "Oba pociągi muszą kończyć trasę na stacji, z której rusza pociąg wynikowy."
            )
        departure = instant(c, c.route.stops[0].departure)
        for run in (a, b):
            wait = (departure - instant(run, run.route.stops[-1].arrival)).total_seconds()
            if not MINIMUM_DWELL <= wait <= MAXIMUM_DWELL:
                raise ValueError(
                    "Od przyjazdu każdego pociągu do wspólnego odjazdu musi upłynąć od 5 do 120 minut."
                )
        stock_a, stock_b = effective_stock(a), effective_stock(b)
        if not stock_a or not stock_b:
            raise ValueError("Oba pociągi muszą mieć przypisane składy.")
        if {w.id for w in stock_a} & {w.id for w in stock_b}:
            raise ValueError("Pociągi nie mogą współdzielić tego samego składu.")
        # If C already feeds another coupling, its consist change could invalidate that operation.
        if db.session.scalar(select(CouplingInput).where(CouplingInput.run_id == c.id)):
            raise ValueError("Najpierw usuń dalsze łączenie pociągu wynikowego.")
        coupling = Coupling(station_id=station_id, output_run_id=c.id, note=note.strip()[:300])
        coupling.inputs = [
            CouplingInput(run_id=a.id, position=1),
            CouplingInput(run_id=b.id, position=2),
        ]
        db.session.add(coupling)
        db.session.commit()
        return coupling
    except Exception:
        db.session.rollback()
        raise


def remove_coupling(coupling):
    # Serialize removal against a concurrent downstream coupling using this output.
    db.session.execute(select(Run).where(Run.id == coupling.output_run_id).with_for_update())
    if db.session.scalar(
        select(CouplingInput).where(CouplingInput.run_id == coupling.output_run_id)
    ):
        raise ValueError("Najpierw usuń dalsze łączenie tego pociągu.")
    db.session.delete(coupling)
    db.session.commit()


def route_is_coupled(route_id):
    ids = select(Run.id).where(Run.route_id == route_id)
    return bool(
        db.session.scalar(
            select(Coupling.id)
            .where(
                or_(
                    Coupling.output_run_id.in_(ids),
                    Coupling.id.in_(
                        select(CouplingInput.coupling_id).where(CouplingInput.run_id.in_(ids))
                    ),
                )
            )
            .limit(1)
        )
    )


def lock_route_runs(route_ids):
    """Serialize changes to base stock/timetables against creation of couplings."""
    return list(
        db.session.scalars(
            select(Run).where(Run.route_id.in_(route_ids)).order_by(Run.id).with_for_update()
        )
    )
