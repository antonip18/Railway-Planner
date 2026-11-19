"""Compatibility entry point; use `flask --app railway run` or `gunicorn 'railway:create_app()'`."""

from railway import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
