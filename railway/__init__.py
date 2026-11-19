import os
import sqlite3
from pathlib import Path

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .config import configuration
from .extensions import csrf, db


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, _):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


def create_app(test_config=None):
    instance = os.getenv("RAILWAY_INSTANCE_PATH", str(Path.cwd() / "instance"))
    app = Flask(
        __name__, instance_relative_config=True, instance_path=str(Path(instance).resolve())
    )
    app.config.from_mapping(configuration(app.instance_path))
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    csrf.init_app(app)
    from . import models  # noqa: F401
    from .cli import register_commands
    from .services.times import display_time
    from .web.admin import admin
    from .web.auth import auth
    from .web.public import public

    for blueprint in (public, admin, auth):
        app.register_blueprint(blueprint)
    register_commands(app)
    app.jinja_env.filters["clock"] = display_time

    @app.context_processor
    def navigation():
        from sqlalchemy import select

        from .models import Dataset

        return {"dataset": db.session.scalar(select(Dataset).limit(1))}

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template(
            "error.html", message="Formularz wygasł. Odśwież stronę i spróbuj ponownie."
        ), 400

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", message="Nie znaleziono strony lub kursu."), 404

    return app
