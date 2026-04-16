from app.extensions import db
from app.models import Comment, Survey


def test_create_comment_rejects_invalid_period(client, login_analyst):
    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202613",
            "comment": "invalid period attempt",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Period must be in YYYYMM format" in response.data


def test_create_and_search_comment_by_ruref(client, login_analyst, app):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "ONS contributor note",
        },
        follow_redirects=True,
    )

    response = client.get("/comments?ruref=12345678901", follow_redirects=True)
    assert response.status_code == 200
    assert b"ONS contributor note" in response.data


def test_deactivated_survey_not_usable_for_new_comments(client, login_admin, app):
    client.post("/admin/surveys/221/toggle-active", follow_redirects=True)

    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202602",
            "comment": "should fail",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Survey must be selected from the configured survey list" in response.data

    with app.app_context():
        assert Comment.query.count() == 0
        survey = db.session.get(Survey, "221")
        assert survey is not None
        assert survey.is_active is False
