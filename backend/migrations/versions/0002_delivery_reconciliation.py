"""Delivery reconciliation fields on messages.

0001 creates the whole schema from the model metadata, so a fresh database
already has these columns. This migration adds them to a database that
stopped at 0001, and is written to be safe either way.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = {
    "sending_since": sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
    "reconciled_by": sa.Column("reconciled_by", sa.String(80), nullable=True),
}


def existing():
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("messages")}


def upgrade():
    present = existing()
    for name, column in COLUMNS.items():
        if name not in present:
            op.add_column("messages", column)


def downgrade():
    present = existing()
    for name in COLUMNS:
        if name in present:
            op.drop_column("messages", name)
