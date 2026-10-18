"""Append-only audit table, replacing the rewritten settings row.

Also copies any entries already accumulated in the legacy `settings` row with
key `audit`. The legacy row is left in place rather than deleted, so an
operator can still inspect it after the upgrade.
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLE = "audit_entries"


def upgrade():
    bind = op.get_bind()
    if TABLE not in sa.inspect(bind).get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(80), nullable=False),
            sa.Column("actor", sa.String(80), nullable=False, server_default="admin"),
            sa.Column("detail", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(f"ix_{TABLE}_created_at", TABLE, ["created_at"])
    legacy = bind.execute(sa.text("SELECT value FROM settings WHERE key = 'audit'")).scalar()
    if not legacy:
        return
    value = json.loads(legacy) if isinstance(legacy, str) else legacy
    rows = [
        {
            "id": str(uuid.uuid4()),
            "kind": entry.get("kind", "settings_changed"),
            "actor": entry.get("actor", "admin"),
            "detail": {k: v for k, v in entry.items() if k not in ["kind", "actor", "at"]},
            "created_at": entry.get("at"),
        }
        for entry in value.get("events", [])
    ]
    if rows:
        bind.execute(
            sa.text(f"INSERT INTO {TABLE} (id, kind, actor, detail, created_at) VALUES (:id, :kind, :actor, :detail, :created_at)"),
            [{**row, "detail": json.dumps(row["detail"])} for row in rows],
        )


def downgrade():
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        op.drop_table(TABLE)
