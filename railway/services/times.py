from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def instant(run, seconds):
    # GTFS time is elapsed from local noon minus 12 hours, including DST days.
    noon = datetime.combine(run.service_date, time(12), WARSAW).astimezone(timezone.utc)
    return noon - timedelta(hours=12) + timedelta(seconds=seconds)


def local_instant(day, clock):
    return datetime.combine(day, clock, WARSAW).astimezone(timezone.utc)


def display_time(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    return f"{hours:02}:{remainder // 60:02}" + (f" (+{days})" if days else "")


def parse_input_time(value):
    from railway.gtfs.normalization import seconds

    return seconds(value + ":00" if len(value.split(":")) == 2 else value)
