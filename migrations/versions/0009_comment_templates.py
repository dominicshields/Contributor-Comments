"""add available comment templates metadata

Revision ID: 0009_comment_templates
Revises: 0008_site_content_help
Create Date: 2026-04-21 00:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0009_comment_templates"
down_revision = "0008_site_content_help"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comment_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wording", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("comment_templates", "is_active", server_default=None)

    template_table = sa.table(
        "comment_templates",
        sa.column("wording", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)
    default_templates = [
        "Contact gave figures over the 'phone",
        "Contact unavailable until ...... recontact",
        "Contributor checking queries and will 'phone back",
        "Contributor unable to complete form by deadline due to ........ will return by .....",
        "Emailed/faxed duplicate form on request",
        "Enforcement call made...",
        "Estimated figures given, correct figures will be sent in asap",
        "Left message with colleague/on voicemail chasing form",
        "Nil return given over the 'phone",
        "No inquiry form received",
        "Requested return of overdue form",
    ]

    op.bulk_insert(
        template_table,
        [
            {
                "wording": wording,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for wording in default_templates
        ],
    )


def downgrade() -> None:
    op.drop_table("comment_templates")
