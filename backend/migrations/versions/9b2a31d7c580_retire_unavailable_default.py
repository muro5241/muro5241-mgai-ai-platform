"""Disable the unavailable 70B model without deleting historical job references."""

import sqlalchemy as sa
from alembic import op

revision = "9b2a31d7c580"
down_revision = "444cda8f1d44"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text("UPDATE models SET enabled=false WHERE id=:id").bindparams(
            id="nvidia/llama-3.1-nemotron-70b-instruct"
        )
    )


def downgrade():
    # Keep the known-unavailable endpoint disabled and all historical data intact.
    pass
