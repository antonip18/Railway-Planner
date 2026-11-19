# Railway

A railway journey planner built with **Python 3.12+, Flask, SQLAlchemy and PostgreSQL**. It imports Polish GTFS timetables, finds journeys with up to two transfers, displays carriage layouts, and models **two complete trains joining into one onward train**. The interface is in Polish.

## Run locally

Linux/macOS, Python 3.12+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
flask --app railway init-db
flask --app railway seed-demo
flask --app railway set-admin-password
flask --app railway run
```

Open **http://127.0.0.1:5000**. SQLite is used when `DATABASE_URL` is unset. The offline demo includes Kraków/Katowice → Warszawa → Gdańsk: search from 07:00 with **no transfers** to see the joined train. It generates a finite calendar around today's date. Administration is at `/admin`; there is no default password.

## PostgreSQL with Docker Compose

```bash
docker compose up -d db
docker compose build web
docker compose run --rm web flask --app railway init-db
docker compose run --rm web flask --app railway seed-demo
docker compose run --rm web flask --app railway set-admin-password
docker compose up -d web
```

Open **http://127.0.0.1:8000**. The application runs through Gunicorn; database and instance files use named volumes. `docker compose down` retains them. The default database password is for local development. For an existing PostgreSQL server, export `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DATABASE` before running the local commands. Environment files are not automatically loaded by the Python app.

## Import real data

The repository includes a small **archived IC snapshot from 10 May 2026**. Use a separate empty database instead of mixing it with the demo:

```bash
export DATABASE_URL="sqlite:///$PWD/instance/ic.db"
flask --app railway init-db
flask --app railway import-gtfs data/ic-2026-05-10.zip --dry-run
flask --app railway import-gtfs data/ic-2026-05-10.zip --report instance/import-report.json
flask --app railway run
```

Try Kraków Główny → Warszawa Centralna on **12 May 2026**, from 07:00. A ZIP or an extracted GTFS directory is accepted. `--agency IC` is the default; repeat the option for other operators or use `--agency ALL`. Download newer feeds from [the publisher](https://mkuran.pl/gtfs/). Reimporting identical input is a no-op; a different feed version requires a fresh database.

**Data correctness:** `trip_id` identifies a source trip, not a physical train. Suffixes are retained for traceability. Only schedules with identical stops, times, access rules and transport mode are merged; all exact operating dates remain. Hours above 24, calendar exceptions and rail/bus legs are preserved. Neither suffixes nor `block_id` imply that passengers stay on board. See [data notes and source credits](data/README.md).

## Whole-train coupling

In **Panel zarządzania → Łączenia**, select two dated incoming runs **A + B** and an outgoing run **C**. Both inputs must terminate where C starts, with 5–120 minutes between each arrival and C's departure. C inherits every carriage of A followed by every carriage of B; its default consist is replaced for that run only. The passenger can continue without a transfer. Cancelling the coupling restores the independent consists. PostgreSQL transactions, ordered row locks and uniqueness constraints prevent reusing an incoming run in concurrent operations.

Carriage layouts and default consists are **illustrative**, retained from the original project. The supplied feed does not establish real coupling operations or vehicle assignments. Those operations are explicit scenarios created in the admin panel, not inferred data.

## Code organization

| Directory | Responsibility |
| --- | --- |
| `railway/models` | Relational timetable, source provenance, stock and coupling entities |
| `railway/gtfs` | CSV/ZIP reader, calendar expansion, validation, deduplication and atomic import |
| `railway/services` | Time-dependent journey search, transfer rules, coupling and route editing |
| `railway/web` | Public, authentication and admin blueprints; thin request handlers |
| `railway/templates`, `static` | Jinja views and shared carriage renderer; no frontend build step |
| `railway/migrations` | Versioned Alembic schema; applied explicitly with `init-db` |
| `tests` | Unit, PostgreSQL integration and Playwright browser tests |

## Checks

```bash
pytest
ruff check .
ruff format --check .
```

PostgreSQL tests require a **disposable** database whose name starts with `railway_test`; they reset its public schema:

```bash
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost/railway_test \
  REAL_GTFS_PATH=data/ic-2026-05-10.zip pytest tests/test_postgres.py
python -m pip install -e '.[ui]'
playwright install chromium
RUN_UI_TESTS=1 pytest tests/test_ui.py
```

GitHub Actions runs the checks, PostgreSQL tests and browser flow. Without the optional environment variables, those integration tests are explicitly skipped. Tests cover calendar exceptions, suffix variants, replacement buses, overnight services, transfers, complete-consist coupling, concurrent conflicts, form validation and all 24 carriage layouts.

## Scope

This is a portfolio application, not live travel information or a reservation system. Search returns up to eight journeys, with a 24-hour boarding horizon and up to two transfers. Only explicit rail/bus schedules in the `Europe/Warsaw` agency timezone are supported; frequency-based feeds are rejected. Maps are schematic. Accessibility filters refer to the illustrative stock. Physical fleet diagrams, incremental feed updates and real-time data are outside the model. Use PostgreSQL for concurrent administration; SQLite is intended for the local demo.

The new schema is intentionally separate from the legacy SQL dump: import the original GTFS files into a new database. Do not apply it over an existing legacy database. Runtime files and secrets stay in ignored `instance/` (override with `RAILWAY_INSTANCE_PATH`). For public deployment, configure HTTPS, `COOKIE_SECURE=1`, a stable random `SECRET_KEY` and access controls around the admin panel.
