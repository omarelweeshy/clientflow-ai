"""Initial ClientFlow schema, durable uniqueness and audit tables."""

from app.db import Base
from app import models  # noqa: F401
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    Base.metadata.drop_all(op.get_bind())
