from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from flask import Flask, redirect, url_for
from flask_login import current_user
from markupsafe import Markup, escape

from .extensions import csrf, db, login_manager
from .models import User
from .seed import seed_reference_data

LOCAL_ENVS = {"dev", "development", "local", "test"}


def _should_run_alembic_for_local(app_env: str, database_url: str) -> bool:
    if app_env == "test":
        return False

    return database_url != "sqlite:///:memory:"


def _run_alembic_upgrade(database_url: str) -> None:
    project_root = Path(__file__).resolve().parent.parent
    alembic_ini = project_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    os.makedirs(app.instance_path, exist_ok=True)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/contributor_comments",
    )
    app.config["APP_ENV"] = os.getenv("APP_ENV", "dev").lower()

    auth_mode_env = os.getenv("AUTH_MODE")
    if app.config["APP_ENV"] in LOCAL_ENVS and auth_mode_env is None:
        raise RuntimeError(
            "AUTH_MODE is not set for a local/dev/test run. "
            "Set AUTH_MODE=local (or AUTH_MODE=sso with proxy headers) and restart."
        )

    app.config["AUTH_MODE"] = (auth_mode_env or "sso").lower()
    app.config["SSO_HEADER_USERNAME"] = os.getenv(
        "SSO_HEADER_USERNAME", "X-Forwarded-User"
    )
    app.config["SSO_HEADER_FULL_NAME"] = os.getenv(
        "SSO_HEADER_FULL_NAME", "X-Forwarded-Name"
    )
    app.config["SSO_AUTO_PROVISION"] = (
        os.getenv("SSO_AUTO_PROVISION", "true").lower() == "true"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DESIGN_SYSTEM_STYLESHEET"] = "design-system/v1/contributor-ons.css"
    app.config["ONS_DESIGN_SYSTEM_VERSION"] = os.getenv(
        "ONS_DESIGN_SYSTEM_VERSION", "73.0.0"
    )

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from .routes.admin import bp as admin_bp
    from .routes.auth import bp as auth_bp
    from .routes.comments import bp as comments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("comments.index"))
        return redirect(url_for("auth.login"))

    @app.context_processor
    def inject_design_system_css_url() -> dict[str, str]:
        stylesheet_path = (
            Path(app.static_folder) / app.config["DESIGN_SYSTEM_STYLESHEET"]
        )
        stylesheet_version = (
            int(stylesheet_path.stat().st_mtime) if stylesheet_path.exists() else 0
        )
        return {
            "ons_design_system_css_url": (
                "https://cdn.ons.gov.uk/sdc/design-system/"
                f"{app.config['ONS_DESIGN_SYSTEM_VERSION']}/css/main.css"
            ),
            "design_system_css_url": url_for(
                "static",
                filename=app.config["DESIGN_SYSTEM_STYLESHEET"],
                v=stylesheet_version,
            ),
            "auth_mode": app.config["AUTH_MODE"],
        }

    @app.after_request
    def disable_cache_for_html(response):
        # Dynamic pages should not be cached to avoid stale UI state across refresh/navigation.
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.template_filter("uk_datetime")
    def uk_datetime_filter(value: Optional[datetime]) -> str:
        if value is None:
            return ""

        london = ZoneInfo("Europe/London")
        return value.astimezone(london).strftime("%d %b %Y %H:%M")

    @app.template_filter("highlight_term")
    def highlight_term_filter(value: Optional[str], term: Optional[str]) -> Markup:
        if value is None:
            return Markup("")

        escaped_value = escape(value)
        if term is None:
            return Markup(str(escaped_value))

        cleaned_term = term.strip()
        if not cleaned_term:
            return Markup(str(escaped_value))

        pattern = re.compile(re.escape(cleaned_term), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda match: f"<mark>{match.group(0)}</mark>", str(escaped_value)
        )
        return Markup(highlighted)

    with app.app_context():
        if app.config["APP_ENV"] in LOCAL_ENVS:
            if _should_run_alembic_for_local(
                app.config["APP_ENV"], app.config["SQLALCHEMY_DATABASE_URI"]
            ):
                _run_alembic_upgrade(app.config["SQLALCHEMY_DATABASE_URI"])
            db.create_all()
            seed_reference_data()
        else:
            _run_alembic_upgrade(app.config["SQLALCHEMY_DATABASE_URI"])

    return app


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    return db.session.get(User, int(user_id))
