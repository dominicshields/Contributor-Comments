"""Add survey metadata fields

Revision ID: 0002_survey_metadata_fields
Revises: 0001_initial_schema
Create Date: 2026-04-16 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_survey_metadata_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("surveys", sa.Column("description", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("surveys", sa.Column("forms_per_period", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint(
        "ck_surveys_forms_per_period_non_negative",
        "surveys",
        "forms_per_period >= 0",
    )
    op.alter_column("surveys", "description", server_default=None)
    op.alter_column("surveys", "forms_per_period", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_surveys_forms_per_period_non_negative", "surveys", type_="check")
    op.drop_column("surveys", "forms_per_period")
    op.drop_column("surveys", "description")
