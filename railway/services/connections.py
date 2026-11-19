"""GTFS transfer rules and explicit train couplings; block_id is never evidence of a through ride."""

from collections import defaultdict

from sqlalchemy import select

from railway.extensions import db
from railway.models import Coupling, TransferRule, TripSource


class ConnectionPolicy:
    def __init__(self, runs):
        self.coupled = {
            item.run_id: c.output_run_id
            for c in db.session.scalars(select(Coupling))
            for item in c.inputs
        }
        self.sources = defaultdict(list)
        route_ids = {r.route_id for r in runs}
        for source in db.session.scalars(
            select(TripSource).where(TripSource.route_id.in_(route_ids))
        ):
            self.sources[source.route_id].append(source)
        self.rules = list(db.session.scalars(select(TransferRule)))
        self.neighbors = defaultdict(set)
        for rule in self.rules:
            if (
                rule.from_station_id is not None
                and rule.to_station_id is not None
                and rule.transfer_type != 3
            ):
                self.neighbors[rule.from_station_id].add(rule.to_station_id)

    def _matches_source(self, rule, side, run):
        if rule.dataset_id != run.route.dataset_id:
            return False
        trip_id = getattr(rule, side + "_trip_id")
        route_id = getattr(rule, side + "_route_id")
        if not trip_id and not route_id:
            return True
        return any(
            (not trip_id or s.trip_id == trip_id)
            and (not route_id or s.gtfs_route_id == route_id)
            and run.service_date.isoformat() in s.dates
            for s in self.sources[run.route_id]
        )

    def connection(self, previous, target, boarding, minimum):
        """Return (kind, minimum seconds), or None when a transfer is forbidden."""
        arrival_stop = previous.run.route.stops[previous.alight]
        departure_stop = target.route.stops[boarding]
        same = arrival_stop.station_id == departure_stop.station_id
        endpoints = previous.alight == len(previous.run.route.stops) - 1 and boarding == 0
        if endpoints and same and self.coupled.get(previous.run.id) == target.id:
            return "stay", 0
        matching = []
        for rule in self.rules:
            if (
                rule.from_station_id is not None
                and rule.from_station_id != arrival_stop.station_id
                or rule.to_station_id is not None
                and rule.to_station_id != departure_stop.station_id
            ):
                continue
            if self._matches_source(rule, "from", previous.run) and self._matches_source(
                rule, "to", target
            ):
                specificity = (
                    (bool(rule.from_trip_id) + bool(rule.to_trip_id)) * 10
                    + bool(rule.from_route_id)
                    + bool(rule.to_route_id)
                )
                matching.append((specificity, rule))
        if matching:
            specificity = max(score for score, _ in matching)
            rules = [r for score, r in matching if score == specificity]
            if any(r.transfer_type == 3 for r in rules):
                return None
            if (
                endpoints
                and any(r.transfer_type == 4 for r in rules)
                and not any(r.transfer_type == 5 for r in rules)
            ):
                return "stay", 0
            return "transfer", max([minimum] + [r.minimum_seconds or 0 for r in rules])
        return ("transfer", minimum) if same else None
