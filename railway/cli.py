import json
import os
from pathlib import Path

import click
from alembic import command
from alembic.config import Config
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .extensions import db


def migration_config():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    return config


@click.command("init-db")
@with_appcontext
def init_db():
    """Apply schema migrations without deleting data."""
    with db.engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    click.echo("Schemat bazy jest aktualny.")


@click.command("set-admin-password")
@click.password_option(confirmation_prompt=True)
@with_appcontext
def set_admin(password):
    """Create/update the local admin password; never store plaintext."""
    if len(password) < 12:
        raise click.ClickException("Użyj co najmniej 12 znaków.")
    path = Path(current_app.instance_path) / "admin-password.hash"
    descriptor = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(generate_password_hash(password))
    click.echo("Hasło administratora zostało ustawione.")


@click.command("import-gtfs")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--agency",
    multiple=True,
    default=("IC",),
    help="Repeat to select agencies; use ALL for every agency.",
)
@click.option(
    "--dry-run", is_flag=True, help="Validate and print a report without changing the database."
)
@click.option(
    "--skip-invalid",
    is_flag=True,
    help="Reject whole invalid trips and include every rejection in the report.",
)
@click.option("--report", type=click.Path(path_type=Path))
@with_appcontext
def import_gtfs(path, agency, dry_run, skip_invalid, report):
    """Import exact dated trips from a GTFS ZIP or directory."""
    from .gtfs import plan_import
    from .gtfs.importer import import_plan

    try:
        plan = plan_import(path, () if "ALL" in agency else agency, strict=not skip_invalid)
        if not dry_run:
            _, created = import_plan(plan)
            click.echo("Import zakończony." if created else "Ten import już istnieje; bez zmian.")
        result = json.dumps(plan.report, ensure_ascii=False, indent=2)
        if report:
            report.write_text(result + "\n", encoding="utf-8")
        click.echo(result)
    except (ValueError, KeyError) as error:
        raise click.ClickException(str(error)) from error


@click.command("seed-demo")
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="First demo service day (defaults to today).",
)
@with_appcontext
def seed_demo(start_date):
    """Create a small offline timetable, including a complete A+B→C coupling."""
    from datetime import date

    from .services.demo import create_demo

    try:
        create_demo(start_date.date() if start_date else date.today())
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    click.echo("Demo: Kraków/Katowice → Warszawa → Gdańsk. Dwa pociągi łączą się w Warszawie.")


def register_commands(app):
    for cmd in (init_db, set_admin, import_gtfs, seed_demo):
        app.cli.add_command(cmd)
