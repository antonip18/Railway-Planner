import os
import secrets
import tempfile
from pathlib import Path


def session_key(instance):
    configured = os.getenv("SECRET_KEY")
    if configured:
        return configured
    key_file = instance / "session.key"
    if not key_file.exists():
        # Publish a complete key atomically, even when multiple workers start together.
        with tempfile.NamedTemporaryFile(mode="w", dir=instance, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(secrets.token_hex(32))
        try:
            os.link(temporary, key_file)
        except FileExistsError:
            pass
        finally:
            temporary.unlink()
    key = key_file.read_text().strip()
    if not key:
        raise RuntimeError("The session key file is empty; configure SECRET_KEY.")
    return key


def configuration(instance_path):
    instance = Path(instance_path)
    instance.mkdir(parents=True, exist_ok=True, mode=0o700)
    return {
        "SECRET_KEY": session_key(instance),
        "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL")
        or "sqlite:///" + str(instance / "railway.db"),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": os.getenv("COOKIE_SECURE") == "1",
        "MAX_CONTENT_LENGTH": 1_000_000,
    }
