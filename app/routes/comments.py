from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import distinct, or_

from ..extensions import db
from ..models import Comment, CommentEdit, Contact, ReportingUnit, Survey, User
from ..validation import is_period_allowed_for_survey, is_valid_period, is_valid_ruref


bp = Blueprint("comments", __name__)
GENERAL_GROUP_KEY = "General"


def _query_flag(name: str, default: bool = False) -> bool:
    values = request.args.getlist(name)
    if not values:
        return default

    raw = values[-1].strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _format_count_for_display(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _survey_order_map() -> dict[str, int]:
    surveys = Survey.query.order_by(Survey.display_order.asc()).all()
    return {survey.code: survey.display_order for survey in surveys}


def _group_comments(comments: list[Comment]) -> OrderedDict[str, list[Comment]]:
    ordered = OrderedDict()
    ordered[GENERAL_GROUP_KEY] = []
    surveys = Survey.query.order_by(Survey.display_order.asc()).all()
    for survey in surveys:
        ordered[survey.code] = []

    for comment in comments:
        if comment.is_general:
            ordered[GENERAL_GROUP_KEY].append(comment)
        else:
            survey_key = comment.survey_code or "Unknown"
            ordered.setdefault(survey_key, []).append(comment)

    return OrderedDict((k, v) for k, v in ordered.items() if v)


def _sort_comments_for_ruref_display(comments: list[Comment]) -> list[Comment]:
    survey_order_map = _survey_order_map()
    return sorted(
        comments,
        key=lambda comment: (
            0 if comment.is_general else 1,
            survey_order_map.get(comment.survey_code or "", 999),
            -int(comment.period),
            -comment.created_at.timestamp(),
        ),
    )


def _contact_key_for_comment(comment: Comment) -> str | None:
    if comment.is_general:
        return None
    return comment.survey_code


def _contact_has_display_name(contact: Contact | None) -> bool:
    if contact is None:
        return False

    return bool(contact.name.strip())


def _contacts_for_ruref(ruref: str) -> dict[str | None, Contact]:
    contacts = Contact.query.filter_by(ruref=ruref).all()
    return {contact.survey_code: contact for contact in contacts}


def _contacts_for_rurefs(rurefs: set[str]) -> dict[str, dict[str | None, Contact]]:
    if not rurefs:
        return {}

    contacts = Contact.query.filter(Contact.ruref.in_(sorted(rurefs))).all()
    contacts_by_ruref: dict[str, dict[str | None, Contact]] = {}
    for contact in contacts:
        contacts_by_ruref.setdefault(contact.ruref, {})[contact.survey_code] = contact

    return contacts_by_ruref


def _sort_contacts_for_display(contacts: list[Contact]) -> list[Contact]:
    survey_order_map = _survey_order_map()
    return sorted(
        contacts,
        key=lambda contact: (
            contact.ruref,
            0 if contact.survey_code is None else 1,
            survey_order_map.get(contact.survey_code or "", 999),
            contact.survey_code or "",
            contact.id,
        ),
    )


def _load_lowest_ruref_comment_groups(limit: int = 10) -> OrderedDict[str, OrderedDict[str, list[Comment]]]:
    rurefs = [
        row[0]
        for row in db.session.query(distinct(Comment.ruref))
        .order_by(Comment.ruref.asc())
        .limit(limit)
        .all()
    ]

    grouped_by_ruref: OrderedDict[str, OrderedDict[str, list[Comment]]] = OrderedDict()
    if not rurefs:
        return grouped_by_ruref

    comments = Comment.query.filter(Comment.ruref.in_(rurefs)).all()
    comments_by_ruref: dict[str, list[Comment]] = {ruref: [] for ruref in rurefs}
    for comment in comments:
        comments_by_ruref.setdefault(comment.ruref, []).append(comment)

    for ruref in rurefs:
        grouped_by_ruref[ruref] = _group_comments(_sort_comments_for_ruref_display(comments_by_ruref[ruref]))

    return grouped_by_ruref


@bp.get("/comments")
@login_required
def index():
    ruref = request.args.get("ruref", "").strip()
    query_text = request.args.get("q", "").strip()
    selected_surveys = request.args.getlist("surveys")
    show_comments = _query_flag("show_comments", default=False)
    show_contacts = _query_flag("show_contacts", default=False)
    search_performed = show_comments or bool(ruref or query_text or selected_surveys)

    surveys = Survey.query.filter_by(is_active=True).order_by(Survey.display_order.asc()).all()
    comments = []
    grouped_results = OrderedDict()
    ruref_groups = OrderedDict()
    contacts_by_ruref: dict[str, dict[str | None, Contact]] = {}
    reporting_units_with_comments = db.session.query(db.func.count(distinct(Comment.ruref))).scalar() or 0
    total_comments = db.session.query(db.func.count(Comment.id)).scalar() or 0

    if show_comments:
        ruref_groups = _load_lowest_ruref_comment_groups()
    elif search_performed:
        comment_query = Comment.query

        if ruref:
            if is_valid_ruref(ruref):
                comment_query = comment_query.filter(Comment.ruref == ruref)
            else:
                flash("RUREF must be exactly 11 numeric characters.", "error")
                comment_query = comment_query.filter(False)

        if selected_surveys:
            comment_query = comment_query.filter(
                or_(Comment.survey_code.in_(selected_surveys), Comment.is_general.is_(True))
            )

        if query_text:
            like_pattern = f"%{query_text}%"
            comment_query = comment_query.filter(
                or_(
                    Comment.comment_text.ilike(like_pattern),
                    Comment.ruref.ilike(like_pattern),
                    Comment.period.ilike(like_pattern),
                    Comment.survey_code.ilike(like_pattern),
                    Comment.author.has(User.full_name.ilike(like_pattern)),
                    Comment.author.has(User.username.ilike(like_pattern)),
                )
            )

        comments = (
            comment_query.order_by(Comment.period.desc(), Comment.created_at.desc()).limit(300).all()
        )
        grouped_results = _group_comments(comments)

    if show_contacts and search_performed:
        result_rurefs: set[str] = set()
        for comment in comments:
            result_rurefs.add(comment.ruref)
        for result_ruref, grouped_comments in ruref_groups.items():
            if grouped_comments:
                result_rurefs.add(result_ruref)

        contacts_by_ruref = _contacts_for_rurefs(result_rurefs)

    return render_template(
        "comments/index.html",
        comments=comments,
        grouped_results=grouped_results,
        ruref_groups=ruref_groups,
        contacts_by_ruref=contacts_by_ruref,
        show_contacts=show_contacts,
        contact_has_display_name=_contact_has_display_name,
        contact_key_for_comment=_contact_key_for_comment,
        search_performed=search_performed,
        show_comments=show_comments,
        reporting_units_with_comments=_format_count_for_display(reporting_units_with_comments),
        total_comments=_format_count_for_display(total_comments),
        surveys=surveys,
        selected_surveys=selected_surveys,
        ruref=ruref,
        q=query_text,
    )


@bp.get("/help")
@login_required
def help_page():
    return render_template("help/index.html")


@bp.get("/contacts-management")
@login_required
def contact_management():
    ruref = request.args.get("ruref", "").strip()
    show_all_contacts = _query_flag("show_all_contacts", default=False)
    search_performed = show_all_contacts or bool(ruref)

    contacts: list[Contact] = []
    if show_all_contacts:
        contacts = Contact.query.all()
    elif ruref:
        if is_valid_ruref(ruref):
            contacts = Contact.query.filter_by(ruref=ruref).all()
        else:
            flash("RUREF must be exactly 11 numeric characters.", "error")

    grouped_contacts: OrderedDict[str, list[Contact]] = OrderedDict()
    for contact in _sort_contacts_for_display(contacts):
        grouped_contacts.setdefault(contact.ruref, []).append(contact)

    return render_template(
        "comments/contact_management.html",
        ruref=ruref,
        show_all_contacts=show_all_contacts,
        search_performed=search_performed,
        grouped_contacts=grouped_contacts,
    )


@bp.post("/comments/new")
@login_required
def create_comment():
    ruref = request.form.get("ruref", "").strip()
    survey_code = request.form.get("survey", "").strip()
    period = request.form.get("period", "").strip()
    comment_text = request.form.get("comment", "").strip()
    is_general = request.form.get("is_general") == "1"
    contact_name = request.form.get("contact_name", "").strip()
    contact_phone = request.form.get("contact_phone", "").strip()
    contact_email = request.form.get("contact_email", "").strip()

    valid = True

    if not is_valid_ruref(ruref):
        flash("Reporting Unit Reference must be exactly 11 numeric characters.", "error")
        valid = False

    if not is_valid_period(period):
        flash("Period must be in YYYYMM format and represent a valid month.", "error")
        valid = False

    survey = None
    contact_survey_code: str | None = None

    if not is_general:
        survey = db.session.get(Survey, survey_code)
        if survey is None or not survey.is_active:
            flash("Survey must be selected from the configured survey list.", "error")
            valid = False
        elif not is_period_allowed_for_survey(survey.code, survey.periodicity, period):
            flash("Period month must match the selected survey periodicity.", "error")
            valid = False
        contact_survey_code = survey_code

    if not comment_text:
        flash("Comment cannot be empty.", "error")
        valid = False

    has_contact_input = bool(contact_name or contact_phone or contact_email)
    existing_contact = None
    if has_contact_input:
        existing_contact = Contact.query.filter_by(ruref=ruref, survey_code=contact_survey_code).first()
        if existing_contact is not None:
            scope = "general comment" if contact_survey_code is None else f"survey {contact_survey_code}"
            flash(
                f"A contact already exists for this reporting unit and {scope}. Edit the existing contact instead.",
                "error",
            )
            return redirect(url_for("comments.edit_contact", contact_id=existing_contact.id))

    if not valid:
        return redirect(url_for("comments.index", ruref=ruref))

    reporting_unit = db.session.get(ReportingUnit, ruref)
    if reporting_unit is None:
        reporting_unit = ReportingUnit(ruref=ruref)
        db.session.add(reporting_unit)

    comment = Comment(
        ruref=ruref,
        survey_code=survey_code if not is_general else None,
        is_general=is_general,
        period=period,
        comment_text=comment_text,
        author_id=current_user.id,
    )
    db.session.add(comment)

    if has_contact_input and existing_contact is None:
        db.session.add(
            Contact(
                ruref=ruref,
                survey_code=contact_survey_code,
                name=contact_name,
                telephone_number=contact_phone,
                email_address=contact_email,
            )
        )

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
    show_contacts = _query_flag("show_contacts", default=False)

    comment_query = Comment.query.filter(Comment.ruref == ruref)

    if selected_surveys:
        comment_query = comment_query.filter(
            or_(Comment.survey_code.in_(selected_surveys), Comment.is_general.is_(True))
        )

    if query_text:
        comment_query = comment_query.filter(Comment.comment_text.ilike(f"%{query_text}%"))

    comments = comment_query.all()
    comments = _sort_comments_for_ruref_display(comments)

    grouped_comments = _group_comments(comments)
    contacts_by_survey = _contacts_for_ruref(ruref)
    surveys = Survey.query.filter_by(is_active=True).order_by(Survey.display_order.asc()).all()

    return render_template(
        "comments/ruref_detail.html",
        ruref=ruref,
        grouped_comments=grouped_comments,
        contacts_by_survey=contacts_by_survey,
        show_contacts=show_contacts,
        contact_has_display_name=_contact_has_display_name,
        contact_key_for_comment=_contact_key_for_comment,
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


@bp.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
@login_required
def edit_contact(contact_id: int):
    contact = db.session.get(Contact, contact_id)
    if contact is None:
        flash("Contact not found.", "error")
        return redirect(url_for("comments.index"))

    if request.method == "POST":
        contact.name = request.form.get("name", "").strip()
        contact.telephone_number = request.form.get("telephone_number", "").strip()
        contact.email_address = request.form.get("email_address", "").strip()
        db.session.commit()
        flash("Contact updated.", "success")
        return redirect(url_for("comments.ruref_detail", ruref=contact.ruref))

    return render_template("comments/edit_contact.html", contact=contact)
