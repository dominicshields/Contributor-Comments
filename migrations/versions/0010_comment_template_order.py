"""add display order for comment templates

Revision ID: 0010_template_order
Revises: 0009_comment_templates
Create Date: 2026-04-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0010_template_order"
down_revision = "0009_comment_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comment_templates",
        sa.Column("display_order", sa.Integer(), nullable=True),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id FROM comment_templates ORDER BY id ASC")
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        bind.execute(
            sa.text(
                "UPDATE comment_templates SET display_order = :display_order WHERE id = :id"
            ),
            {"display_order": index, "id": row.id},
        )

    op.alter_column("comment_templates", "display_order", nullable=False)


def downgrade() -> None:
    op.drop_column("comment_templates", "display_order")
