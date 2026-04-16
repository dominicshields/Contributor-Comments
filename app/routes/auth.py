from __future__ import annotations

import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import User


bp = Blueprint("auth", __name__, url_prefix="/auth")


def _sso_sign_in_from_headers() -> tuple[bool, str | None]:
    username_header = current_app.config["SSO_HEADER_USERNAME"]
    full_name_header = current_app.config["SSO_HEADER_FULL_NAME"]
    auto_provision = current_app.config["SSO_AUTO_PROVISION"]

    username = request.headers.get(username_header, "").strip()
    if not username:
        username = request.environ.get("REMOTE_USER", "").strip()

    full_name = request.headers.get(full_name_header, "").strip() or username

    if not username:
        return False, (
            f"SSO identity header '{username_header}' was not found. "
            "Check your reverse proxy / identity provider header mapping."
        )

    user = User.query.filter_by(username=username).first()

    if user is None:
        if not auto_provision:
            return False, "Your SSO identity is valid but no application user exists. Contact an administrator."

        user = User(
            username=username,
            full_name=full_name,
            is_admin=False,
            # SSO users do not authenticate with local passwords.
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
        )
        db.session.add(user)
        db.session.commit()
    elif full_name and user.full_name != full_name:
        user.full_name = full_name
        db.session.commit()

    login_user(user)
    return True, None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("comments.index"))

    auth_mode = current_app.config.get("AUTH_MODE", "sso")

    if auth_mode == "sso":
        ok, error_message = _sso_sign_in_from_headers()
        if ok:
            return redirect(url_for("comments.index"))
        return render_template("auth/login.html", sso_error=error_message)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("auth/login.html", sso_error=None)

        login_user(user)
        return redirect(url_for("comments.index"))

    return render_template("auth/login.html", sso_error=None)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
