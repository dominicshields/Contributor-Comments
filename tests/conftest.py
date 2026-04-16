from __future__ import annotations

import os

import pytest

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login_admin(client):
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "Password123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return response


@pytest.fixture()
def login_analyst(client):
    response = client.post(
        "/auth/login",
        data={"username": "analyst1", "password": "Password123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return response


@pytest.fixture()
def admin_user(app):
    with app.app_context():
        return User.query.filter_by(username="admin").first()
