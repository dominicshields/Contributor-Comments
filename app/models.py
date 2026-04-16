from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="author")
    edits: Mapped[list[CommentEdit]] = relationship("CommentEdit", back_populates="editor")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class ReportingUnit(db.Model):
    __tablename__ = "reporting_units"

    ruref: Mapped[str] = mapped_column(String(11), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="reporting_unit")


class Survey(db.Model):
    __tablename__ = "surveys"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    forms_per_period: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    comments: Mapped[list[Comment]] = relationship("Comment", back_populates="survey")

    __table_args__ = (
        CheckConstraint("forms_per_period >= 0", name="ck_surveys_forms_per_period_non_negative"),
    )


class Comment(db.Model):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ruref: Mapped[str] = mapped_column(String(11), ForeignKey("reporting_units.ruref"), nullable=False, index=True)
    survey_code: Mapped[str] = mapped_column(String(3), ForeignKey("surveys.code"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    reporting_unit: Mapped[ReportingUnit] = relationship("ReportingUnit", back_populates="comments")
    survey: Mapped[Survey] = relationship("Survey", back_populates="comments")
    author: Mapped[User] = relationship("User", back_populates="comments")
    edit_history: Mapped[list[CommentEdit]] = relationship("CommentEdit", back_populates="comment", order_by="desc(CommentEdit.edited_at)")

    __table_args__ = (
        CheckConstraint("length(period) = 6", name="ck_comments_period_len"),
        CheckConstraint("length(ruref) = 11", name="ck_comments_ruref_len"),
    )


class CommentEdit(db.Model):
    __tablename__ = "comment_edits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id"), nullable=False, index=True)
    editor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    previous_text: Mapped[str] = mapped_column(Text, nullable=False)
    new_text: Mapped[str] = mapped_column(Text, nullable=False)

    comment: Mapped[Comment] = relationship("Comment", back_populates="edit_history")
    editor: Mapped[User] = relationship("User", back_populates="edits")

    __table_args__ = (UniqueConstraint("id", "comment_id", name="uq_comment_edits_id_comment"),)
