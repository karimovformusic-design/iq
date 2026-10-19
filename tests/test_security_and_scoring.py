from mindora.constants import AGE_BANDS, age_band_for
from mindora.models import Question
from mindora.scoring import score_answers
from mindora.settings import Settings, is_authorized_admin


def test_age_range_bands_cover_7_through_70_without_gaps():
    assert age_band_for(7) == "7-12"
    assert age_band_for(12) == "7-12"
    assert age_band_for(13) == "13-17"
    assert age_band_for(18) == "18-30"
    assert age_band_for(31) == "31-50"
    assert age_band_for(51) == "51-70"
    assert age_band_for(70) == "51-70"
    assert [band[0] for band in AGE_BANDS] == [7, 13, 18, 31, 51]


def test_age_validation_rejects_outside_supported_range():
    for age in (6, 71, -1):
        try:
            age_band_for(age)
        except ValueError:
            pass
        else:
            raise AssertionError(f"age {age} should have been rejected")


def test_admin_authorization_uses_only_exact_numeric_telegram_id():
    configured = frozenset({772233445})
    assert is_authorized_admin(772233445, configured)
    assert not is_authorized_admin(772233446, configured)
    assert not is_authorized_admin(None, configured)
    assert not is_authorized_admin(772233445, frozenset())


def test_production_requires_postgresql_not_ephemeral_sqlite():
    try:
        Settings(DATABASE_URL="sqlite+aiosqlite:///./local.db", APP_ENV="production")
    except ValueError as error:
        assert "PostgreSQL" in str(error)
    else:
        raise AssertionError("Production must not silently use container-local SQLite.")


def test_postgres_sslmode_is_normalized_for_asyncpg():
    configured = Settings(
        DATABASE_URL="postgresql://user:password@db.example/mindora?sslmode=require&application_name=mindora",
        APP_ENV="production",
    )
    assert configured.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in configured.database_url
    assert "sslmode=" not in configured.database_url
    assert "application_name=mindora" in configured.database_url


def test_iq_score_uses_correct_answer_key_and_disclaims_official_iq():
    questions = [
        Question(id=1, category_slug="iq", age_band="18-30", prompt_uz="?", options_uz=["a", "b"], correct_index=1),
        Question(id=2, category_slug="iq", age_band="18-30", prompt_uz="?", options_uz=["a", "b"], correct_index=0),
    ]
    score, maximum, report = score_answers("iq", questions, [1, 1])
    assert (score, maximum) == (1, 2)
    assert "rasmiy IQ bahosi emas" in report


def test_wellbeing_report_is_non_diagnostic():
    question = Question(
        id=3,
        category_slug="wellbeing",
        age_band="31-50",
        prompt_uz="?",
        options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha"],
        factor="wellbeing",
    )
    score, maximum, report = score_answers("wellbeing", [question], [0])
    assert (score, maximum) == (0, 3)
    assert "tashxis emas" in report
