"""Worker freshness without printing database credentials."""

from datetime import timedelta

from .config import Settings
from .database import Database
from .models import Control, now


def main():
    settings = Settings.from_env()
    settings.validate()
    db = Database(settings)
    try:
        with db.sessions() as session:
            control = session.get(Control, 1)
            return (
                0
                if control
                and control.worker_seen_at
                and control.worker_seen_at > now() - timedelta(seconds=150)
                else 1
            )
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
