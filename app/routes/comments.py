from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Comment, CommentEdit, ReportingUnit, Survey
from ..validation import is_valid_period, is_valid_ruref


bp = Blueprint("comments", __name__)


def _survey_order_map() -> dict[str, int]:
    surveys = Survey.query.order_by(Survey.display_order.asc()).all()
    return {survey.code: survey.display_order for survey in surveys}


def _group_comments(comments: list[Comment]) -> OrderedDict[str, list[Comment]]:
    ordered = OrderedDict()
    surveys = Survey.query.order_by(Survey.display_order.asc()).all()
    for survey in surveys:
        ordered[survey.code] = []

    for comment in comments:
        ordered.setdefault(comment.survey_code, []).append(comment)

    return OrderedDict((k, v) for k, v in ordered.items() if v)


@bp.get("/comments")
@login_required
def index():
    ruref = request.args.get("ruref", "").strip()
    query_text = request.args.get("q", "").strip()
    selected_surveys = request.args.getlist("surveys")
    search_performed = bool(ruref or query_text or selected_surveys)

    surveys = Survey.query.filter_by(is_active=True).order_by(Survey.display_order.asc()).all()
    comments = []
    grouped_results = OrderedDict()

    if search_performed:
        comment_query = Comment.query

        if ruref:
            if is_valid_ruref(ruref):
                comment_query = comment_query.filter(Comment.ruref == ruref)
            else:
                flash("RUREF must be exactly 11 numeric characters.", "error")
                comment_query = comment_query.filter(False)

        if selected_surveys:
            comment_query = comment_query.filter(Comment.survey_code.in_(selected_surveys))

        if query_text:
            like_pattern = f"%{query_text}%"
            comment_query = comment_query.filter(
                or_(
                    Comment.comment_text.ilike(like_pattern),
                    Comment.ruref.ilike(like_pattern),
                    Comment.period.ilike(like_pattern),
                    Comment.survey_code.ilike(like_pattern),
                )
            )

        comments = (
            comment_query.order_by(Comment.period.desc(), Comment.created_at.desc()).limit(300).all()
        )
        grouped_results = _group_comments(comments)

    return render_template(
        "comments/index.html",
        comments=comments,
        grouped_results=grouped_results,
        search_performed=search_performed,
        surveys=surveys,
        selected_surveys=selected_surveys,
        ruref=ruref,
        q=query_text,
    )


@bp.post("/comments/new")
@login_required
def create_comment():
    ruref = request.form.get("ruref", "").strip()
    survey_code = request.form.get("survey", "").strip()
    period = request.form.get("period", "").strip()
    comment_text = request.form.get("comment", "").strip()

    valid = True

    if not is_valid_ruref(ruref):
        flash("Reporting Unit Reference must be exactly 11 numeric characters.", "error")
        valid = False

    if not is_valid_period(period):
        flash("Period must be in YYYYMM format and represent a valid month.", "error")
        valid = False

    survey = db.session.get(Survey, survey_code)
    if survey is None or not survey.is_active:
        flash("Survey must be selected from the configured survey list.", "error")
        valid = False

    if not comment_text:
        flash("Comment cannot be empty.", "error")
        valid = False

    if not valid:
        return redirect(url_for("comments.index", ruref=ruref))

    reporting_unit = db.session.get(ReportingUnit, ruref)
    if reporting_unit is None:
        reporting_unit = ReportingUnit(ruref=ruref)
        db.session.add(reporting_unit)

    comment = Comment(
        ruref=ruref,
        survey_code=survey_code,
        period=period,
        comment_text=comment_text,
        author_id=current_user.id,
    )
    db.session.add(comment)
    db.session.commit()

    flash("Comment saved.", "success")
    return redirect(url_for("comments.ruref_detail", ruref=ruref))


@bp.get("/ruref/<ruref>")
@login_required
def ruref_detail(ruref: str):
    if not is_valid_ruref(ruref):
        flash("RUREF must be exactly 11 numeric characters.", "error")
        return redirect(url_for("comments.index"))

    selected_surveys = request.args.getlist("surveys")
    query_text = request.args.get("q", "").strip()

    survey_order_map = _survey_order_map()

    comment_query = Comment.query.filter(Comment.ruref == ruref)

    if selected_surveys:
        comment_query = comment_query.filter(Comment.survey_code.in_(selected_surveys))

    if query_text:
        comment_query = comment_query.filter(Comment.comment_text.ilike(f"%{query_text}%"))

    comments = comment_query.all()
    comments.sort(
        key=lambda c: (
            survey_order_map.get(c.survey_code, 999),
            -int(c.period),
            c.created_at.timestamp() * -1,
        )
    )

    grouped_comments = _group_comments(comments)
    surveys = Survey.query.filter_by(is_active=True).order_by(Survey.display_order.asc()).all()

    return render_template(
        "comments/ruref_detail.html",
        ruref=ruref,
        grouped_comments=grouped_comments,
        surveys=surveys,
        selected_surveys=selected_surveys,
        q=query_text,
    )


@bp.route("/comments/<int:comment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_comment(comment_id: int):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        flash("Comment not found.", "error")
        return redirect(url_for("comments.index"))

    if request.method == "POST":
        new_text = request.form.get("comment", "").strip()
        if not new_text:
            flash("Comment text cannot be empty.", "error")
            return render_template("comments/edit_comment.html", comment=comment)

        if new_text != comment.comment_text:
            edit = CommentEdit(
                comment_id=comment.id,
                editor_id=current_user.id,
                previous_text=comment.comment_text,
                new_text=new_text,
            )
            comment.comment_text = new_text
            db.session.add(edit)
            db.session.commit()
            flash("Comment updated.", "success")
        else:
            flash("No changes were made.", "info")

        return redirect(url_for("comments.ruref_detail", ruref=comment.ruref))

    return render_template("comments/edit_comment.html", comment=comment)
