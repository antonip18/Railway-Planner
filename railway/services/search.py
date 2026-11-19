"""Time-dependent journey search with bounded transfers and a 24-hour departure horizon."""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from heapq import heappop, heappush
from itertools import count

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from railway.extensions import db
from railway.models import Carriage, RouteVariant, Run, Stop, Train

from .connections import ConnectionPolicy
from .stock import supports
from .times import WARSAW, instant, local_instant


@dataclass(frozen=True)
class Leg:
    run: Run
    board: int
    alight: int
    connection: str = "start"

    @property
    def departure(self):
        return instant(self.run, self.run.route.stops[self.board].departure)

    @property
    def arrival(self):
        return instant(self.run, self.run.route.stops[self.alight].arrival)

    @property
    def local_departure(self):
        return self.departure.astimezone(WARSAW)

    @property
    def local_arrival(self):
        return self.arrival.astimezone(WARSAW)


@dataclass(frozen=True)
class Journey:
    legs: tuple
    transfers: int

    @property
    def minutes(self):
        return int((self.legs[-1].arrival - self.legs[0].departure).total_seconds() // 60)


def load_runs(day):
    max_time = db.session.scalar(select(func.max(Stop.departure))) or 0
    # Include services starting on a previous calendar date, whose GTFS hours exceed 24.
    earliest = day - timedelta(days=max_time // 86400 + 1)
    return list(
        db.session.scalars(
            select(Run)
            .where(Run.service_date.between(earliest, day + timedelta(days=2)))
            .options(
                joinedload(Run.route)
                .joinedload(RouteVariant.train)
                .selectinload(Train.carriages)
                .joinedload(Carriage.carriage_type),
                joinedload(Run.route).selectinload(RouteVariant.stops).joinedload(Stop.station),
            )
        ).unique()
    )


def search_journeys(
    start,
    end,
    day,
    clock,
    max_transfers=2,
    minimum_minutes=5,
    wheelchair=False,
    bicycle=False,
    limit=8,
):
    if start == end:
        raise ValueError("Wybierz różne stacje początkową i końcową.")
    if not 0 <= max_transfers <= 2 or not 0 <= minimum_minutes <= 120:
        raise ValueError("Dozwolone są 0–2 przesiadki i 0–120 minut na przesiadkę.")
    earliest = local_instant(day, clock)
    horizon = earliest + timedelta(hours=24)
    runs = [
        r
        for r in load_runs(day)
        if r.route.stops
        and instant(r, r.route.stops[-1].arrival) >= earliest
        and instant(r, r.route.stops[0].departure) <= horizon
    ]
    policy = ConnectionPolicy(runs)
    by_station = defaultdict(list)
    sequence = count()
    supported = {}
    for run in runs:
        supported[run.id] = supports(run, wheelchair, bicycle)
        if not supported[run.id]:
            continue
        for index, stop in enumerate(run.route.stops[:-1]):
            departure = instant(run, stop.departure)
            if earliest <= departure <= horizon:
                # Non-pickup calls remain available for explicit in-seat continuation only.
                by_station[stop.station_id].append((departure, run.id, index, run))
    for entries in by_station.values():
        entries.sort(key=lambda item: (item[0], item[1], item[2]))
    departure_times = {station: [e[0] for e in entries] for station, entries in by_station.items()}
    heap = [(earliest, next(sequence), start, (), 0)]
    labels, results, seen_results = {}, [], set()
    while heap and len(results) < limit:
        arrival, _, station, path, transfers = heappop(heap)
        if station == end and path:
            signature = tuple((leg.run.id, leg.board, leg.alight) for leg in path)
            if signature not in seen_results:
                results.append(Journey(path, transfers))
                seen_results.add(signature)
            continue
        if len(path) >= 8:
            continue
        used = {leg.run.id for leg in path}
        candidates = {station} | (policy.neighbors.get(station, set()) if path else set())
        for boarding_station in candidates:
            entries = by_station.get(boarding_station, [])
            offset = bisect_left(departure_times.get(boarding_station, []), arrival)
            for departure, run_id, boarding, run in entries[offset:]:
                if run_id in used:
                    continue
                kind, wait = "start", 0
                if path:
                    connection = policy.connection(path[-1], run, boarding, minimum_minutes * 60)
                    if connection is None:
                        continue
                    kind, wait = connection
                next_transfers = transfers + (kind == "transfer")
                if next_transfers > max_transfers or departure < arrival + timedelta(seconds=wait):
                    continue
                if kind != "stay" and (
                    not run.route.stops[boarding].pickup
                    or (path and not path[-1].run.route.stops[path[-1].alight].drop_off)
                ):
                    continue
                for alighting in range(boarding + 1, len(run.route.stops)):
                    stop = run.route.stops[alighting]
                    # Keep an endpoint without alighting for possible in-seat continuation.
                    if not stop.drop_off and alighting != len(run.route.stops) - 1:
                        continue
                    if stop.station_id == end and not stop.drop_off:
                        continue
                    leg = Leg(run, boarding, alighting, kind)
                    if leg.arrival > horizon + timedelta(hours=24):
                        continue
                    key = (
                        run_id,
                        boarding,
                        alighting,
                        next_transfers,
                        path[0].run.id if path else run_id,
                    )
                    if key in labels and labels[key] <= leg.arrival:
                        continue
                    labels[key] = leg.arrival
                    heappush(
                        heap,
                        (
                            leg.arrival,
                            next(sequence),
                            stop.station_id,
                            path + (leg,),
                            next_transfers,
                        ),
                    )
    return results
