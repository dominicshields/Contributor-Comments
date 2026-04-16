from app.models import User


def test_sso_login_creates_user_and_redirects(client, app):
    app.config["AUTH_MODE"] = "sso"

    response = client.get(
        "/auth/login",
        headers={"X-Forwarded-User": "sso.user@ons.gov.uk", "X-Forwarded-Name": "SSO User"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/comments")

    with app.app_context():
        user = User.query.filter_by(username="sso.user@ons.gov.uk").first()
        assert user is not None
        assert user.full_name == "SSO User"
        assert user.is_admin is False
