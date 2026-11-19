import hashlib
import json
import math
import re

from .reader import FeedError


def seconds(value):
    if not re.fullmatch(r"\d{1,3}:\d{2}:\d{2}", value):
        raise FeedError(f"Invalid or missing GTFS time: {value!r}")
    hour, minute, second = map(int, value.split(":"))
    if hour >= 168 or minute >= 60 or second >= 60:
        raise FeedError(f"GTFS time out of range: {value}")
    return hour * 3600 + minute * 60 + second


def identity(trip, route):
    # Provider extension, then rider-facing fallback. NEVER strip suffixes from trip_id.
    number = trip.get("plk_train_number") or trip.get("trip_short_name") or trip["trip_id"]
    agency = route.get("agency_id") or "unknown"
    return f"{agency}:{number}", agency, number


def signature(train_identity, category, mode, stops):
    payload = [train_identity, category, mode, stops]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def normalized_stops(rows, stations):
    result = []
    previous_departure = -1
    seen_sequences = set()
    for row in sorted(rows, key=lambda r: int(r["stop_sequence"])):
        sequence = int(row["stop_sequence"])
        if sequence < 0 or sequence in seen_sequences:
            raise FeedError("Invalid or repeated stop_sequence.")
        seen_sequences.add(sequence)
        stop_id = row["stop_id"]
        if stop_id not in stations:
            raise FeedError(f"Unknown station: {stop_id}")
        station = stations[stop_id]
        arrival, departure = seconds(row["arrival_time"]), seconds(row["departure_time"])
        if arrival < previous_departure or departure < arrival:
            raise FeedError("Stop times are not chronological (use GTFS hours above 24).")
        previous_departure = departure
        if row.get("pickup_type", "0") not in ("", "0", "1", "2", "3") or row.get(
            "drop_off_type", "0"
        ) not in ("", "0", "1", "2", "3"):
            raise FeedError("Unknown pickup/drop_off type.")
        result.append(
            {
                "station_key": station["key"],
                "arrival": arrival,
                "departure": departure,
                "platform": row.get("platform") or station["platform"] or None,
                "track": row.get("track") or None,
                "pickup": row.get("pickup_type", "0") in ("", "0"),
                "drop_off": row.get("drop_off_type", "0") in ("", "0"),
            }
        )
    if len(result) < 2:
        raise FeedError("Trip needs at least two stops.")
    return result


def station_records(reader):
    raw = {}
    for row in reader.rows("stops.txt"):
        key = row["stop_id"]
        if not key or key in raw:
            raise FeedError(f"Empty or duplicate stop_id: {key!r}")
        raw[key] = row
    result = {}
    for key, row in raw.items():
        parent_id = row.get("parent_station")
        parent = raw.get(parent_id) if parent_id else row
        if parent is None:
            raise FeedError(f"Unknown parent_station: {parent_id}")
        try:
            lat, lon = (
                float(parent.get("stop_lat") or row["stop_lat"]),
                float(parent.get("stop_lon") or row["stop_lon"]),
            )
            if (
                not math.isfinite(lat)
                or not math.isfinite(lon)
                or not -90 <= lat <= 90
                or not -180 <= lon <= 180
            ):
                raise ValueError()
        except ValueError:
            # Entrances/generic nodes may lack coordinates and are not used by trips.
            if row.get("location_type", "0") not in ("", "0", "1"):
                continue
            raise FeedError(f"Invalid coordinates: {key}") from None
        result[key] = {
            "key": parent_id or key,
            "name": parent["stop_name"],
            "latitude": lat,
            "longitude": lon,
            "platform": row.get("platform_code") or "",
        }
    return result
