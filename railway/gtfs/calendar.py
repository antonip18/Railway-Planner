from collections import defaultdict
from datetime import datetime, timedelta

from .reader import FeedError

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise FeedError(f"Invalid GTFS date: {value}") from exc


def service_dates(reader):
    """Materialize finite service days, then apply additions AND removals."""
    dates = defaultdict(set)
    seen = set()
    for row in reader.rows("calendar.txt"):
        service = row["service_id"]
        if service in seen:
            raise FeedError(f"Duplicate calendar service: {service}")
        seen.add(service)
        start, end = parse_date(row["start_date"]), parse_date(row["end_date"])
        if not 0 <= (end - start).days <= 3660:
            raise FeedError("Calendar range must be ordered and at most ten years.")
        if any(row[d] not in ("0", "1") for d in WEEKDAYS):
            raise FeedError("Calendar weekday flags must be 0 or 1.")
        current = start
        while current <= end:
            if row[WEEKDAYS[current.weekday()]] == "1":
                dates[service].add(current)
            current += timedelta(days=1)
        dates[service]  # Preserve an explicitly empty service.
    exceptions = set()
    for row in reader.rows("calendar_dates.txt"):
        service, day = row["service_id"], parse_date(row["date"])
        if (service, day) in exceptions:
            raise FeedError(f"Duplicate calendar exception: {service}/{day}")
        exceptions.add((service, day))
        if row["exception_type"] == "1":
            dates[service].add(day)
        elif row["exception_type"] == "2":
            dates[service].discard(day)
        else:
            raise FeedError("exception_type must be 1 or 2.")
    if not dates:
        raise FeedError("No calendar.txt/calendar_dates.txt services found.")
    return dates
