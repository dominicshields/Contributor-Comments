"""Add survey periodicity field

Revision ID: 0003_survey_periodicity_field
Revises: 0002_survey_metadata_fields
Create Date: 2026-04-17 00:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_survey_periodicity_field"
down_revision = "0002_survey_metadata_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("surveys", sa.Column("periodicity", sa.String(length=50), nullable=False, server_default=""))
    op.alter_column("surveys", "periodicity", server_default=None)


def downgrade() -> None:
    op.drop_column("surveys", "periodicity")
