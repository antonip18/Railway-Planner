"""Synthetic display stock, derived deterministically from a public train identity."""

import hashlib
from dataclasses import asdict

from sqlalchemy import select

from railway.extensions import db
from railway.models import Carriage, CarriageType, Coupling, RouteVariant, Train

from .carriage_catalog import TYPY_WAGONOW, wybierz_szablon_skladu


def ensure_types():
    existing = set(db.session.scalars(select(CarriageType.id)))
    for definition in TYPY_WAGONOW:
        if definition.id_typu in existing:
            continue
        elements, seats = definition.builder()
        db.session.add(
            CarriageType(
                id=definition.id_typu,
                name=definition.nazwa,
                rows=definition.liczba_rzedow,
                columns=definition.liczba_kolumn,
                compartment=definition.czy_przedzialowy,
                layout={
                    "elements": [asdict(e) for e in elements],
                    "seats": [asdict(s) for s in seats],
                },
            )
        )
    db.session.flush()


def assign_default_stock(train, type_ids=None):
    if train.carriages:
        return
    seed = int.from_bytes(hashlib.sha256(train.identity.encode()).digest()[:8], "big")
    ids = type_ids if type_ids is not None else wybierz_szablon_skladu(train.category, seed)
    for position, type_id in enumerate(ids, 1):
        if db.session.get(CarriageType, type_id) is None:
            raise ValueError("Nieznany typ wagonu.")
        train.carriages.append(Carriage(type_id=type_id, position=position))


def effective_stock(run, seen=None):
    """A coupled output contains every carriage from A followed by every carriage from B."""
    seen = set() if seen is None else seen
    if run.id in seen:
        raise ValueError("Cykliczne łączenie pociągów.")
    if run.route.mode == "bus":
        return []
    seen = seen | {run.id}
    coupling = db.session.scalar(select(Coupling).where(Coupling.output_run_id == run.id))
    if coupling:
        return [
            carriage for source in coupling.inputs for carriage in effective_stock(source.run, seen)
        ]
    return list(run.route.train.carriages)


def carriage_view(carriage):
    kind = carriage.carriage_type
    return {
        "id": carriage.id,
        "source_train": carriage.train.label,
        "name": kind.name,
        "rows": kind.rows,
        "columns": kind.columns,
        **kind.layout,
    }


def supports(run, wheelchair=False, bicycle=False):
    if not wheelchair and not bicycle:
        return True
    seats = [seat for c in effective_stock(run) for seat in c.carriage_type.layout["seats"]]
    return (not wheelchair or any(s["czy_dla_niepelnosprawnych"] for s in seats)) and (
        not bicycle or any(s["czy_dla_rowerzystow"] for s in seats)
    )


def add_carriage(train_id, type_id):
    from .coupling import lock_route_runs, route_is_coupled

    try:
        routes = list(
            db.session.scalars(select(RouteVariant.id).where(RouteVariant.train_id == train_id))
        )
        lock_route_runs(routes)
        train = db.session.scalar(select(Train).where(Train.id == train_id).with_for_update())
        kind = db.session.get(CarriageType, type_id) if type_id else None
        if not train or not kind:
            raise ValueError("Wybierz pociąg i typ wagonu.")
        if any(route_is_coupled(route_id) for route_id in routes):
            raise ValueError(
                "Najpierw usuń łączenia tego pociągu; zmiana taboru wpłynęłaby na ich składy."
            )
        db.session.expire(train, ["carriages"])
        if len(train.carriages) >= 30:
            raise ValueError("Bazowy skład może mieć najwyżej 30 wagonów.")
        position = max((c.position for c in train.carriages), default=0) + 1
        train.carriages.append(Carriage(type_id=kind.id, position=position))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
