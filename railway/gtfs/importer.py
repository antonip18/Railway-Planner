"""Persist one validated feed in a single transaction. Never generate SQL text by interpolation."""

from datetime import date

from sqlalchemy import select

from railway.extensions import db
from railway.models import (
    Dataset,
    RouteVariant,
    Run,
    Station,
    Stop,
    Train,
    TransferRule,
    TripSource,
)
from railway.services.stock import assign_default_stock, ensure_types

from .reader import FeedError


def import_plan(plan):
    existing = db.session.scalar(select(Dataset).where(Dataset.fingerprint == plan.fingerprint))
    if existing:
        return existing, False
    if db.session.scalar(select(Dataset.id).limit(1)) or db.session.scalar(
        select(RouteVariant.id).limit(1)
    ):
        raise FeedError(
            "Import wymaga pustej bazy. Identyczny plik można wczytać ponownie; nowy rozkład wczytaj do nowej bazy, aby nie mieszać wersji danych."
        )
    try:
        report = plan.report
        dataset = Dataset(
            fingerprint=plan.fingerprint,
            name=plan.metadata.get("feed_publisher_name") or "GTFS",
            version=plan.metadata.get("feed_version"),
            start_date=date.fromisoformat(report["first_service_date"])
            if report["first_service_date"]
            else None,
            end_date=date.fromisoformat(report["last_service_date"])
            if report["last_service_date"]
            else None,
            attributions=plan.attributions,
            report=report,
        )
        db.session.add(dataset)
        db.session.flush()
        stations = {}
        for key, item in sorted(plan.stations.items()):
            station = Station(
                source_key=key,
                name=item["name"],
                latitude=item["latitude"],
                longitude=item["longitude"],
            )
            db.session.add(station)
            stations[key] = station
        trains = {}
        ensure_types()
        for key, item in sorted(plan.trains.items()):
            train = Train(**item)
            db.session.add(train)
            trains[key] = train
        db.session.flush()
        for train in trains.values():
            assign_default_stock(train)
        variants = {}
        for sig, item in sorted(plan.variants.items()):
            stops = item["stops"]
            label = f"{stations[stops[0]['station_key']].name} → {stations[stops[-1]['station_key']].name}"
            variant = RouteVariant(
                train_id=trains[item["identity"]].id,
                dataset_id=dataset.id,
                signature=sig,
                name=label,
                category=item["category"],
                mode=item["mode"],
            )
            for index, stop in enumerate(stops):
                variant.stops.append(
                    Stop(
                        sequence=index,
                        station_id=stations[stop["station_key"]].id,
                        **{k: v for k, v in stop.items() if k != "station_key"},
                    )
                )
            variant.runs = [Run(service_date=d) for d in sorted(item["dates"])]
            db.session.add(variant)
            variants[sig] = variant
        db.session.flush()
        db.session.execute(
            db.insert(TripSource),
            [
                {
                    **{k: v for k, v in item.items() if k != "signature"},
                    "dataset_id": dataset.id,
                    "route_id": variants[item["signature"]].id,
                }
                for item in plan.sources
            ],
        )
        for item in plan.transfers:
            db.session.add(
                TransferRule(
                    dataset_id=dataset.id,
                    transfer_type=item["type"],
                    from_station_id=stations[item["from_station_key"]].id
                    if item["from_station_key"]
                    else None,
                    to_station_id=stations[item["to_station_key"]].id
                    if item["to_station_key"]
                    else None,
                    **{
                        k: v
                        for k, v in item.items()
                        if not k.endswith("_station_key") and k != "type"
                    },
                )
            )
        db.session.commit()
        return dataset, True
    except Exception:
        db.session.rollback()
        raise
