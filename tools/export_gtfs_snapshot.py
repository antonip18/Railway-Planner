"""Make a small, reproducible timetable-only GTFS subset; never rewrite trip IDs or times.

Usage: python tools/export_gtfs_snapshot.py SOURCE.zip data/ic-2026-05-10.zip --agency IC
Optional route geometry is omitted; agency/feed/attribution records are preserved.
"""

import argparse
import csv
import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from railway.gtfs.reader import FeedReader


def export_snapshot(source, output, agency="IC"):
    with FeedReader(source) as reader:
        routes = [r for r in reader.rows("routes.txt") if r.get("agency_id") == agency]
        route_ids = {r["route_id"] for r in routes}
        trips = [r for r in reader.rows("trips.txt") if r["route_id"] in route_ids]
        if not trips:
            raise ValueError(f"No trips for agency {agency!r}.")
        trip_ids = {r["trip_id"] for r in trips}
        services = {r["service_id"] for r in trips}
        stop_times = [r for r in reader.rows("stop_times.txt") if r["trip_id"] in trip_ids]
        transfers = [
            r
            for r in reader.rows("transfers.txt")
            if all(
                not r.get(k) or r[k] in ids
                for k, ids in (
                    ("from_trip_id", trip_ids),
                    ("to_trip_id", trip_ids),
                    ("from_route_id", route_ids),
                    ("to_route_id", route_ids),
                )
            )
        ]
        stop_ids = {r["stop_id"] for r in stop_times}
        stop_ids.update(r[k] for r in transfers for k in ("from_stop_id", "to_stop_id") if r.get(k))
        stops = {r["stop_id"]: r for r in reader.rows("stops.txt")}
        pending = list(stop_ids)
        while pending:
            parent = stops[pending.pop()].get("parent_station")
            if parent and parent not in stop_ids:
                stop_ids.add(parent)
                pending.append(parent)
        # These optional references are meaningless when geometry is not distributed.
        for trip in trips:
            trip.pop("shape_id", None)
        for stop in stop_times:
            stop.pop("shape_dist_traveled", None)
        tables = {
            "agency.txt": [r for r in reader.rows("agency.txt") if r.get("agency_id") == agency],
            "routes.txt": routes,
            "trips.txt": trips,
            "stop_times.txt": stop_times,
            "stops.txt": [row for key, row in stops.items() if key in stop_ids],
            "calendar.txt": [r for r in reader.rows("calendar.txt") if r["service_id"] in services],
            "calendar_dates.txt": [
                r for r in reader.rows("calendar_dates.txt") if r["service_id"] in services
            ],
            "transfers.txt": transfers,
            "feed_info.txt": list(reader.rows("feed_info.txt")),
            "attributions.txt": list(reader.rows("attributions.txt")),
        }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, rows in sorted(tables.items()):
            if not rows:
                continue
            content = io.StringIO(newline="")
            writer = csv.DictWriter(content, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, content.getvalue().encode("utf-8"))
    return len(trips)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--agency", default="IC")
    args = parser.parse_args()
    count = export_snapshot(args.source, args.output, args.agency)
    print(f"Saved {count} source trips to {args.output}.")
