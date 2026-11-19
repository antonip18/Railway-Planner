"""Pure import planning: validate and deduplicate without connecting to a database."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from .calendar import service_dates
from .normalization import identity, normalized_stops, signature, station_records
from .reader import FeedError, FeedReader


@dataclass
class ImportPlan:
    fingerprint: str
    stations: dict
    trains: dict
    variants: dict
    sources: list
    transfers: list
    metadata: dict
    attributions: list
    report: dict


def plan_import(path, agencies=("IC",), strict=True):
    with FeedReader(path) as reader:
        fingerprint = reader.fingerprint(agencies)
        if next(reader.rows("frequencies.txt"), None):
            raise FeedError(
                "Frequency-based services are not supported; use an explicit timetable feed."
            )
        agency_rows = {a.get("agency_id", ""): a for a in reader.rows("agency.txt")}
        if not agency_rows:
            raise FeedError("agency.txt is required (supported timezone: Europe/Warsaw).")
        for key, agency in agency_rows.items():
            if (not agencies or key in agencies) and agency.get(
                "agency_timezone"
            ) != "Europe/Warsaw":
                raise FeedError("This importer supports Europe/Warsaw agency time only.")
        routes = {}
        for row in reader.rows("routes.txt"):
            if row["route_id"] in routes:
                raise FeedError(f"Duplicate route_id: {row['route_id']}")
            routes[row["route_id"]] = row
        trips = {}
        skipped_modes = 0
        for row in reader.rows("trips.txt"):
            route = routes.get(row["route_id"])
            if route is None:
                raise FeedError(f"Unknown route_id: {row['route_id']}")
            if agencies and route.get("agency_id") not in agencies:
                continue
            mode_code = int(route["route_type"])
            if (
                mode_code not in (2, 3)
                and not 100 <= mode_code <= 199
                and not 700 <= mode_code <= 799
            ):
                skipped_modes += 1
                continue
            if row["trip_id"] in trips:
                raise FeedError(f"Duplicate trip_id: {row['trip_id']}")
            row = dict(row, mode="rail" if mode_code == 2 or 100 <= mode_code <= 199 else "bus")
            trips[row["trip_id"]] = row
        dates = service_dates(reader)
        stations = station_records(reader)
        stop_rows = defaultdict(list)
        for row in reader.rows("stop_times.txt"):
            if row["trip_id"] in trips:
                stop_rows[row["trip_id"]].append(row)
        trains, variants, sources, errors = {}, {}, [], []
        names = defaultdict(Counter)
        for trip_id, trip in sorted(trips.items()):
            route = routes[trip["route_id"]]
            try:
                if trip["service_id"] not in dates:
                    raise FeedError(f"Unknown service_id: {trip['service_id']}")
                stops = normalized_stops(stop_rows[trip_id], stations)
            except (ValueError, KeyError) as exc:
                message = f"{trip_id}: {exc}"
                if strict:
                    raise FeedError(message) from exc
                errors.append(message)
                continue
            key, agency, number = identity(trip, route)
            category = trip.get("plk_category_code") or route.get("route_short_name") or "REG"
            name = trip.get("plk_train_name") or ""
            names[key][name] += 1
            trains.setdefault(
                key,
                {
                    "identity": key,
                    "agency": agency,
                    "number": number,
                    "name": name,
                    "category": category,
                },
            )
            sig = signature(key, category, trip["mode"], stops)
            variant = variants.setdefault(
                sig,
                {
                    "signature": sig,
                    "identity": key,
                    "category": category,
                    "mode": trip["mode"],
                    "stops": stops,
                    "dates": set(),
                    "source_ids": [],
                },
            )
            variant["dates"].update(dates[trip["service_id"]])
            variant["source_ids"].append(trip_id)
            sources.append(
                {
                    "trip_id": trip_id,
                    "signature": sig,
                    "gtfs_route_id": trip["route_id"],
                    "service_id": trip["service_id"],
                    "block_id": trip.get("block_id") or None,
                    "dates": sorted(d.isoformat() for d in dates[trip["service_id"]]),
                }
            )
        for key, counts in names.items():
            trains[key]["name"] = sorted(counts, key=lambda n: (-counts[n], n))[0]
        if not variants:
            raise FeedError("No supported trips in the selected agencies.")
        valid_ids = {s["trip_id"] for s in sources}
        transfers = []
        for row in reader.rows("transfers.txt"):
            if (
                row.get("from_trip_id")
                and row["from_trip_id"] not in valid_ids
                or row.get("to_trip_id")
                and row["to_trip_id"] not in valid_ids
            ):
                continue
            kind = int(row.get("transfer_type") or 0)
            if kind not in range(6):
                raise FeedError("Unknown transfer_type.")
            if kind in (4, 5) and not (row.get("from_trip_id") and row.get("to_trip_id")):
                raise FeedError("Linked trips need from_trip_id and to_trip_id.")
            minimum = int(row["min_transfer_time"]) if row.get("min_transfer_time") else None
            if minimum is not None and minimum < 0 or kind == 2 and minimum is None:
                raise FeedError("Invalid min_transfer_time.")
            item = {"type": kind, "minimum_seconds": minimum}
            for side in ("from", "to"):
                stop_key = row.get(f"{side}_stop_id")
                if stop_key and stop_key not in stations:
                    raise FeedError(f"Unknown transfer stop: {stop_key}")
                item[f"{side}_station_key"] = stations[stop_key]["key"] if stop_key else None
                for field in ("trip_id", "route_id"):
                    item[f"{side}_{field}"] = row.get(f"{side}_{field}") or None
            transfers.append(item)
        canonical_stations = {}
        for row in sorted(stations.values(), key=lambda x: x["key"]):
            canonical_stations.setdefault(row["key"], row)
        used = {stop["station_key"] for v in variants.values() for stop in v["stops"]}
        used.update(t[k] for t in transfers for k in ("from_station_key", "to_station_key") if t[k])
        canonical_stations = {k: v for k, v in canonical_stations.items() if k in used}
        all_dates = sorted({d for v in variants.values() for d in v["dates"]})
        metadata = next(reader.rows("feed_info.txt"), {})
        report = {
            "source_fingerprint": fingerprint,
            "agencies": list(agencies),
            "source_trips": len(trips),
            "commercial_trains": len(trains),
            "schedule_variants": len(variants),
            "identical_trip_aliases": len(sources) - len(variants),
            "dated_runs": sum(len(v["dates"]) for v in variants.values()),
            "stations": len(canonical_stations),
            "replacement_bus_variants": sum(v["mode"] == "bus" for v in variants.values()),
            "transfer_types": dict(sorted(Counter(str(t["type"]) for t in transfers).items())),
            "first_service_date": all_dates[0].isoformat() if all_dates else None,
            "last_service_date": all_dates[-1].isoformat() if all_dates else None,
            "published_start_date": metadata.get("feed_start_date") or None,
            "published_end_date": metadata.get("feed_end_date") or None,
            "skipped_modes": skipped_modes,
            "rejected_trips": errors,
            "synthetic_fields": ["carriage layouts", "default train consists"],
            "couplings_inferred_from_suffixes": 0,
        }
        return ImportPlan(
            fingerprint,
            canonical_stations,
            trains,
            variants,
            sources,
            transfers,
            metadata,
            list(reader.rows("attributions.txt")),
            report,
        )
