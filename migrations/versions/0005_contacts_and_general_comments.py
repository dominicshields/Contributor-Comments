"""Add contacts and general comments support

Revision ID: 0005_contacts_general
Revises: 0004_survey_periodicity_allowed
Create Date: 2026-04-18 09:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_contacts_general"
down_revision = "0004_survey_periodicity_allowed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    comment_columns = {column["name"] for column in inspector.get_columns("comments")}
    if "is_general" not in comment_columns:
        op.add_column(
            "comments",
            sa.Column("is_general", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("comments", "is_general", server_default=None)

    if "survey_code" in comment_columns:
        op.alter_column("comments", "survey_code", nullable=True)

    table_names = set(inspector.get_table_names())
    if "contacts" not in table_names:
        op.create_table(
            "contacts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("ruref", sa.String(length=11), nullable=False),
            sa.Column("survey_code", sa.String(length=3), nullable=True),
            sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("telephone_number", sa.String(length=50), nullable=False, server_default=""),
            sa.Column("email_address", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("length(ruref) = 11", name="ck_contacts_ruref_len"),
            sa.ForeignKeyConstraint(["ruref"], ["reporting_units.ruref"]),
            sa.ForeignKeyConstraint(["survey_code"], ["surveys.code"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ruref", "survey_code", name="uq_contacts_ruref_survey"),
        )

    contact_indexes = {index["name"] for index in inspector.get_indexes("contacts")}
    if op.f("ix_contacts_ruref") not in contact_indexes:
        op.create_index(op.f("ix_contacts_ruref"), "contacts", ["ruref"], unique=False)
    if op.f("ix_contacts_survey_code") not in contact_indexes:
        op.create_index(op.f("ix_contacts_survey_code"), "contacts", ["survey_code"], unique=False)

    op.alter_column("contacts", "name", server_default=None)
    op.alter_column("contacts", "telephone_number", server_default=None)
    op.alter_column("contacts", "email_address", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_contacts_survey_code"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_ruref"), table_name="contacts")
    op.drop_table("contacts")

    op.drop_column("comments", "is_general")
    op.alter_column("comments", "survey_code", nullable=False)
