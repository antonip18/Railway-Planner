"""Stream CSV tables from a directory or ZIP; IDs always remain strings."""

import csv
import hashlib
import io
from pathlib import Path
from zipfile import ZipFile

TABLES = (
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stops.txt",
    "stop_times.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "transfers.txt",
    "feed_info.txt",
    "attributions.txt",
    "frequencies.txt",
)


class FeedError(ValueError):
    pass


class FeedReader:
    def __init__(self, path):
        self.path = Path(path)
        self.zip = None if self.path.is_dir() else ZipFile(self.path)
        self.names = {}
        if self.zip:
            for entry in self.zip.infolist():
                name = Path(entry.filename).name
                if name in TABLES:
                    if name in self.names:
                        raise FeedError(f"Duplicate table: {name}")
                    if entry.file_size > 250_000_000:
                        raise FeedError(f"Table too large: {name}")
                    self.names[name] = entry.filename
        else:
            self.names = {name: name for name in TABLES if (self.path / name).is_file()}
        for required in ("routes.txt", "trips.txt", "stops.txt", "stop_times.txt"):
            if required not in self.names:
                self.close()
                raise FeedError(f"Missing {required}")

    def rows(self, name):
        if name not in self.names:
            return
        source = self.zip.open(self.names[name]) if self.zip else (self.path / name).open("rb")
        with source, io.TextIOWrapper(source, encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                yield {key: (value or "").strip() for key, value in row.items() if key is not None}

    def fingerprint(self, agencies):
        digest = hashlib.sha256(("railway-import-v1:" + ",".join(sorted(agencies))).encode())
        for name in sorted(self.names):
            digest.update(name.encode())
            source = self.zip.open(self.names[name]) if self.zip else (self.path / name).open("rb")
            with source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    def close(self):
        if self.zip:
            self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
