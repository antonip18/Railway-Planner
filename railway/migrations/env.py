from alembic import context

from railway import models  # noqa: F401
from railway.extensions import db


def migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=db.metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    migrations(connection)
else:
    from railway import create_app

    with create_app().app_context(), db.engine.connect() as connection:
        migrations(connection)
