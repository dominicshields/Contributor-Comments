"""Enforce allowed survey periodicity values

Revision ID: 0004_survey_periodicity_allowed
Revises: 0003_survey_periodicity_field
Create Date: 2026-04-17 01:05:00
"""

from alembic import op


revision = "0004_survey_periodicity_allowed"
down_revision = "0003_survey_periodicity_field"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE surveys
        SET periodicity = 'Other'
        WHERE periodicity IS NULL
           OR periodicity = ''
           OR periodicity NOT IN ('Annual', 'Quarterly', 'Monthly', 'Other')
        """
    )
    op.create_check_constraint(
        "ck_surveys_periodicity_allowed",
        "surveys",
        "periodicity IN ('Annual', 'Quarterly', 'Monthly', 'Other')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_surveys_periodicity_allowed", "surveys", type_="check")
