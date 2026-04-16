"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-16 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reporting_units",
        sa.Column("ruref", sa.String(length=11), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ruref"),
    )

    op.create_table(
        "surveys",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("display_order"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ruref", sa.String(length=11), nullable=False),
        sa.Column("survey_code", sa.String(length=3), nullable=False),
        sa.Column("period", sa.String(length=6), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(period) = 6", name="ck_comments_period_len"),
        sa.CheckConstraint("length(ruref) = 11", name="ck_comments_ruref_len"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ruref"], ["reporting_units.ruref"]),
        sa.ForeignKeyConstraint(["survey_code"], ["surveys.code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_period"), "comments", ["period"], unique=False)
    op.create_index(op.f("ix_comments_ruref"), "comments", ["ruref"], unique=False)
    op.create_index(op.f("ix_comments_survey_code"), "comments", ["survey_code"], unique=False)

    op.create_table(
        "comment_edits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("editor_id", sa.Integer(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_text", sa.Text(), nullable=False),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "comment_id", name="uq_comment_edits_id_comment"),
    )
    op.create_index(op.f("ix_comment_edits_comment_id"), "comment_edits", ["comment_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_comment_edits_comment_id"), table_name="comment_edits")
    op.drop_table("comment_edits")

    op.drop_index(op.f("ix_comments_survey_code"), table_name="comments")
    op.drop_index(op.f("ix_comments_ruref"), table_name="comments")
    op.drop_index(op.f("ix_comments_period"), table_name="comments")
    op.drop_table("comments")

    op.drop_table("users")
    op.drop_table("surveys")
    op.drop_table("reporting_units")
