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


def test_show_comments_returns_lowest_ten_rurefs_grouped_for_display(client, login_analyst):
    test_rows = [
        ("00000000005", "221", "202601", "ruref 5 older"),
        ("00000000005", "221", "202602", "ruref 5 newer"),
        ("00000000005", "241", "202603", "ruref 5 second survey"),
        ("00000000002", "241", "202601", "ruref 2"),
        ("00000000011", "221", "202601", "ruref 11 should be excluded"),
    ]

    for ruref_number in range(1, 12):
        client.post(
            "/comments/new",
            data={
                "ruref": f"{ruref_number:011d}",
                "survey": "221",
                "period": "202601",
                "comment": f"seed comment {ruref_number}",
            },
            follow_redirects=True,
        )

    for ruref, survey, period, text in test_rows:
        client.post(
            "/comments/new",
            data={
                "ruref": ruref,
                "survey": survey,
                "period": period,
                "comment": text,
            },
            follow_redirects=True,
        )

    response = client.get("/comments?show_comments=1", follow_redirects=True)

    assert response.status_code == 200
    assert b"RUREF 00000000001" in response.data
    assert b"RUREF 00000000010" in response.data
    assert b"RUREF 00000000011" not in response.data
    assert response.data.index(b"RUREF 00000000002") < response.data.index(b"RUREF 00000000005")
    assert response.data.index(b"Survey 221") < response.data.index(b"Survey 241")
    assert response.data.index(b"ruref 5 newer") < response.data.index(b"ruref 5 older")


def test_search_tab_displays_reporting_unit_and_comment_totals(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "first",
        },
        follow_redirects=True,
    )
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "241",
            "period": "202602",
            "comment": "second",
        },
        follow_redirects=True,
    )
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678902",
            "survey": "221",
            "period": "202603",
            "comment": "third",
        },
        follow_redirects=True,
    )

    response = client.get("/comments", follow_redirects=True)

    assert response.status_code == 200
    assert b"Number of Reporting Units with comments: 2" in response.data
    assert b"Total comments: 3" in response.data

    def test_comment_search_highlights_search_term_in_results(client, login_analyst):
        client.post(
            "/comments/new",
            data={
                "ruref": "12345678901",
                "survey": "221",
                "period": "202601",
                "comment": "This is a contributor note.",
            },
            follow_redirects=True,
        )

        response = client.get("/comments?q=contributor", follow_redirects=True)

        assert response.status_code == 200
        assert b"<mark>contributor</mark>" in response.data
