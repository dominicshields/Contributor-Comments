from app.validation import is_valid_period, is_valid_ruref


def test_ruref_validation():
    assert is_valid_ruref("12345678901")
    assert not is_valid_ruref("123")
    assert not is_valid_ruref("1234567890A")


def test_period_validation():
    assert is_valid_period("202601")
    assert is_valid_period("199001")
    assert not is_valid_period("202613")
    assert not is_valid_period("20260A")
    assert not is_valid_period("2026")
