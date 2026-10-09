"""First administrator only. Password via protected file or terminal, never argv."""

import argparse
import getpass
from pathlib import Path

from sqlalchemy import select

from .config import Settings
from .database import Database
from .models import Control, User, Workspace
from .registry import seed
from .security import audit, email, hash_password


def create_admin(db, address, name, password):
    address = email(address)
    if not 12 <= len(password) <= 128 or not 2 <= len(name.strip()) <= 80:
        raise ValueError("Use a 12–128 character password and a 2–80 character name")
    seed(db)
    with db.sessions.begin() as session:
        session.scalar(select(Control).where(Control.id == 1).with_for_update())
        if session.scalar(select(User.id).where(User.role == "admin")):
            raise ValueError(
                "An administrator already exists; use the authenticated admin workflow"
            )
        user = User(
            email=address,
            name=name.strip(),
            password_hash=hash_password(password),
            role="admin",
            credits=100,
        )
        session.add(user)
        session.flush()
        session.add(
            Workspace(
                owner_id=user.id,
                name="MGAI Studio",
                description="Bağımsız proje çalışma alanı",
            )
        )
        audit(session, user.id, "admin.bootstrapped", user.id)
        return user.id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="MGAI Admin")
    parser.add_argument("--password-file")
    args = parser.parse_args()
    password = (
        Path(args.password_file).read_text().rstrip("\r\n")
        if args.password_file
        else getpass.getpass("Admin password (12+ characters): ")
    )
    settings = Settings.from_env()
    settings.validate()
    db = Database(settings)
    try:
        create_admin(db, args.email, args.name, password)
        print("First administrator created. No password or provider key was logged.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
