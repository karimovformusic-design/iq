import pytest

from mindora.registration import normalize_registration_name, parse_registration_age


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Nosirjon  ", "Nosirjon"),
        ("G‘ulom    O‘g‘li", "G‘ulom O‘g‘li"),
        ("Каримов", "Каримов"),
        ("O'Connor", "O'Connor"),
    ],
)
def test_registration_names_support_unicode_and_normalize_spaces(value, expected):
    assert normalize_registration_name(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "12345", "---", "x" * 129])
def test_registration_names_reject_blank_or_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_registration_name(value)


@pytest.mark.parametrize(("value", "expected"), [("7", 7), ("70", 70), (" 18 ", 18)])
def test_registration_age_accepts_supported_integer_range(value, expected):
    assert parse_registration_age(value) == expected


@pytest.mark.parametrize("value", ["6", "71", "18 yosh", "18.5", ""])
def test_registration_age_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_registration_age(value)
