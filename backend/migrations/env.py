import os

from alembic import context
from sqlalchemy import create_engine, pool

from mgai.models import Base


def run():
    engine = create_engine(os.environ["DATABASE_URL"], poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run()
