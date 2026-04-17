from __future__ import annotations

import pytest

from app import create_app


def test_create_app_requires_explicit_auth_mode_for_local_runs(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("AUTH_MODE", raising=False)

    with pytest.raises(RuntimeError, match="AUTH_MODE is not set"):
        create_app()
