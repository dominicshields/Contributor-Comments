"""widen reference fields for ASHE support

Revision ID: 0011_reference_field_for_ashe
Revises: 0010_template_order
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_reference_field_for_ashe"
down_revision = "0010_template_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reporting_units") as batch_op:
        batch_op.alter_column(
            "ruref",
            existing_type=sa.String(length=11),
            type_=sa.String(length=20),
        )

    with op.batch_alter_table("comments") as batch_op:
        batch_op.drop_constraint("ck_comments_ruref_len", type_="check")
        batch_op.alter_column(
            "ruref",
            existing_type=sa.String(length=11),
            type_=sa.String(length=20),
        )

    with op.batch_alter_table("contacts") as batch_op:
        batch_op.drop_constraint("ck_contacts_ruref_len", type_="check")
        batch_op.alter_column(
            "ruref",
            existing_type=sa.String(length=11),
            type_=sa.String(length=20),
        )


def downgrade() -> None:
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.alter_column(
            "ruref",
            existing_type=sa.String(length=20),
            type_=sa.String(length=11),
        )
        batch_op.create_check_constraint("ck_contacts_ruref_len", "length(ruref) = 11")

    with op.batch_alter_table("comments") as batch_op:
        batch_op.alter_column(
            "ruref",
            existing_type=sa.String(length=20),
            type_=sa.String(length=11),
        )
        batch_op.create_check_constraint("ck_comments_ruref_len", "length(ruref) = 11")

    with op.batch_alter_table("reporting_units") as batch_op:
        batch_op.alter_column(
            "ruref",
            existing_type=sa.String(length=20),
            type_=sa.String(length=11),
        )
