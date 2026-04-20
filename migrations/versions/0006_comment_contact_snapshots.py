"""Add contact snapshot fields to comments.

Revision ID: 0006_comment_contact_snapshots
Revises: 0005_contacts_general
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_comment_contact_snapshots"
down_revision = "0005_contacts_general"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comments",
        sa.Column("contact_name_snapshot", sa.String(length=120), nullable=False, server_default=""),
    )
    op.add_column(
        "comments",
        sa.Column("contact_phone_snapshot", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "comments",
        sa.Column("contact_email_snapshot", sa.String(length=255), nullable=False, server_default=""),
    )

    connection = op.get_bind()

    contacts_table = sa.table(
        "contacts",
        sa.column("ruref", sa.String()),
        sa.column("survey_code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("telephone_number", sa.String()),
        sa.column("email_address", sa.String()),
    )
    comments_table = sa.table(
        "comments",
        sa.column("id", sa.Integer()),
        sa.column("ruref", sa.String()),
        sa.column("survey_code", sa.String()),
        sa.column("is_general", sa.Boolean()),
        sa.column("contact_name_snapshot", sa.String()),
        sa.column("contact_phone_snapshot", sa.String()),
        sa.column("contact_email_snapshot", sa.String()),
    )

    contacts = connection.execute(
        sa.select(
            contacts_table.c.ruref,
            contacts_table.c.survey_code,
            contacts_table.c.name,
            contacts_table.c.telephone_number,
            contacts_table.c.email_address,
        )
    ).fetchall()

    contacts_by_scope: dict[tuple[str, str | None], tuple[str, str, str]] = {}
    for row in contacts:
        contacts_by_scope[(row.ruref, row.survey_code)] = (
            row.name or "",
            row.telephone_number or "",
            row.email_address or "",
        )

    comments = connection.execute(
        sa.select(
            comments_table.c.id,
            comments_table.c.ruref,
            comments_table.c.survey_code,
            comments_table.c.is_general,
        )
    ).fetchall()

    for row in comments:
        scope_key = (row.ruref, None if row.is_general else row.survey_code)
        name, phone, email = contacts_by_scope.get(scope_key, ("", "", ""))
        connection.execute(
            comments_table.update()
            .where(comments_table.c.id == row.id)
            .values(
                contact_name_snapshot=name,
                contact_phone_snapshot=phone,
                contact_email_snapshot=email,
            )
        )

    op.alter_column("comments", "contact_name_snapshot", server_default=None)
    op.alter_column("comments", "contact_phone_snapshot", server_default=None)
    op.alter_column("comments", "contact_email_snapshot", server_default=None)


def downgrade() -> None:
    op.drop_column("comments", "contact_email_snapshot")
    op.drop_column("comments", "contact_phone_snapshot")
    op.drop_column("comments", "contact_name_snapshot")
