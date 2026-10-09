"""Offline deployment migration task; runtime service never receives owner credentials."""

import os

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql

from .config import postgres_url


def grant_runtime(owner_url, password):
    with psycopg.connect(
        owner_url.replace("postgresql+psycopg://", "postgresql://")
    ) as connection:
        if not connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname='mgai_app'"
        ).fetchone():
            connection.execute(
                sql.SQL(
                    "CREATE ROLE mgai_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
                ).format(sql.Literal(password))
            )
        else:
            connection.execute(
                sql.SQL(
                    "ALTER ROLE mgai_app PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
                ).format(sql.Literal(password))
            )
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        connection.execute("GRANT USAGE ON SCHEMA public TO mgai_app")
        connection.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mgai_app"
        )
        connection.execute(
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mgai_app"
        )
        connection.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mgai_app"
        )
        connection.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO mgai_app"
        )


if __name__ == "__main__":
    os.environ["DATABASE_URL"] = postgres_url(os.environ["DATABASE_URL"])
    command.upgrade(Config("alembic.ini"), "head")
    password = os.getenv("APP_DB_PASSWORD") or os.getenv("MGAI_DB_APP_PASSWORD")
    if password:
        grant_runtime(os.environ["DATABASE_URL"], password)
    print("Migrations completed. Runtime role provisioned when configured.")
