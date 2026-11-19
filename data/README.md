# GTFS data and interpretation

The supplied source is the **Polish Trains GTFS** feed published by [Mikołaj Kuranowski](https://mkuran.pl/gtfs/), based on PKP Polskie Linie Kolejowe S.A. open data and, for other operators in the full feed, Koleje Mazowieckie. The original publication version is `2026-05-10T02:45:21.908913+02:00`; declared coverage is 10 May–9 June 2026. Earlier service dates are retained because overnight trains can originate before that interval.

## What is included

`ic-2026-05-10.zip` is a **processed, timetable-only subset** of the user's original feed: agency IC, its routes, trips, stops and parents, calendars and applicable transfers. Original trip IDs, train numbers, times, dates and attribution records are unchanged. Unused operators/stops, `shapes.txt` and its optional `shape_id` / `shape_dist_traveled` references are omitted. No schedules or coupling facts were invented. The app does not contact the publisher at runtime.

Reproduce the subset after installing the project:

```bash
python tools/export_gtfs_snapshot.py ORIGINAL_GTFS_DIRECTORY data/ic-2026-05-10.zip --agency IC
```

`original-import-report.json` describes the supplied full feed filtered to IC; `snapshot-import-report.json` describes the shipped subset. Their fingerprints differ because their input tables differ. The normalized schedules, dated source records and transfer rules were compared and are identical. Fingerprints hash the selected-agency configuration and relevant CSV bytes; they are not the ZIP's file hash.

| Imported concept | Count |
| --- | ---: |
| Original IC trip records | 3,732 |
| Public train identities | 579 |
| Exact schedule variants | 1,221 |
| Additional identical-schedule aliases | 2,511 |
| Dated runs | 18,833 |
| Stations and stops | 532 |
| Replacement-bus schedule variants | 78 |
| Timed transfer rules (`transfer_type=1`) | 431 |
| Rejected trips / inferred couplings | 0 / 0 |

## Why suffixes cannot be removed blindly

The model separates `Train` (public operator + train number), `RouteVariant` (exact schedule), `Run` (variant on a service date) and `TripSource` (original GTFS identity and dates). For example, the source contains many records of **1638/9 Orzeszkowa**. A shared train number does not guarantee identical times, a single physical consist or a coupling operation. `_LEG0`, `_LEG1` and `_LEG2` may describe rail/bus/rail portions. Dropping the bus portion and joining the rail portions would fabricate a through train.

A variant signature includes the public identity, category, mode, ordered station visits, second-precision times, platform/track and boarding/alighting flags. Different times remain different variants; repeated visits to one station are retained. Exact duplicates share a variant and union their **finite** service-date sets, while every original source record remains traceable in `trip_sources`.

`calendar.txt` supplies bounded weekday rules; `calendar_dates.txt` adds/removes individual dates. Times such as `25:15:00` belong to the previous service date. The time conversion follows GTFS's local-noon-minus-12-hours anchor, including daylight-saving transitions. Unknown platform/track values remain empty. PRM/bicycle features and carriage consists are synthetic UI fixtures, not GTFS evidence. On-request pickup/drop-off values 2/3 are conservatively excluded from ordinary boarding/alighting because the app does not model booking conditions.

The source contains timed transfers (type 1), which still require a transfer. Explicit type 4 links would permit an in-seat continuation; type 5 would force alighting, type 3 forbids transfer, and type 2 provides a minimum transfer time. The publisher explicitly warns that `block_id` is not reliable evidence of in-seat travel for this feed. Whole-train couplings are therefore configured separately, with two inputs and one output on specific dates.

## Source documentation and attribution

- [GTFS Schedule Reference](https://gtfs.org/documentation/schedule/reference/): trips, stop times, calendars, transfers and time semantics.
- [PolishTrainsGTFS](https://github.com/MKuranowski/PolishTrainsGTFS): provider extensions, trip-ID stability and source limitations. The provider notes that timed connections and carriage-transfer information are unavailable from the upstream PLK API; do not infer physical operations from its generated transfer rows.
- [PKP PLK open data](https://www.plk-sa.pl/klienci-i-kontrahenci/api-otwarte-dane).
- [Koleje Mazowieckie public-information reuse terms](https://bip.mazowieckie.com.pl/pl/ponowne-wykorzystywanie-informacji-sektora-publicznego), retained in the original attribution records even though this subset selects IC.

The snapshot is transformed archival public timetable data, not an official or current timetable. Dataset terms and original attribution requirements remain separate from this application's code. Feed attribution is also displayed in the website footer.
