"""Regression against the supplied public IC timetable, not a generated fixture."""

import json
from pathlib import Path

from railway.gtfs import plan_import

DATA = Path(__file__).resolve().parents[1] / "data"


def test_shipped_snapshot_has_exact_schedules_and_no_invented_couplings():
    plan = plan_import(DATA / "ic-2026-05-10.zip")
    assert plan.report == json.loads((DATA / "snapshot-import-report.json").read_text())
    assert len(plan.trains) == 579
    assert len(plan.variants) == 1221
    assert sum(len(v["dates"]) for v in plan.variants.values()) == 18833
    assert len(plan.sources) == 3732
    assert any("_LEG" in source["trip_id"] for source in plan.sources)
    assert {rule["type"] for rule in plan.transfers} == {1}
    assert plan.report["couplings_inferred_from_suffixes"] == 0
