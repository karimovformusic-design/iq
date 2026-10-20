from mindora.constants import AGE_BANDS, age_band_for
from mindora.models import Question
from mindora.scoring import score_answers
from mindora.seed_data import IQ_QUESTION_BANK_SIZE, build_question_bank
from mindora.settings import Settings, is_authorized_admin
from mindora.broadcast_worker import _is_unreachable_bad_request


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
        ADMIN_IDS="123456789",
    )
    assert configured.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in configured.database_url
    assert "sslmode=" not in configured.database_url
    assert "application_name=mindora" in configured.database_url


def test_production_requires_a_numeric_admin_allowlist():
    try:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:password@db.example/mindora",
            APP_ENV="production",
        )
    except ValueError as error:
        assert "ADMIN_IDS" in str(error)
    else:
        raise AssertionError("Production must not start without an administrator ID.")
    configured = Settings(
        DATABASE_URL="postgresql+asyncpg://user:password@db.example/mindora",
        APP_ENV="production",
        ADMIN_IDS="123456789",
    )
    assert configured.admin_ids == frozenset({123456789})


def test_unreachable_telegram_recipients_are_classified_as_blocked():
    class FakeTelegramError:
        def __init__(self, message):
            self.message = message

    assert _is_unreachable_bad_request(FakeTelegramError("Bad Request: chat not found"))
    assert _is_unreachable_bad_request(FakeTelegramError("Forbidden: user is deactivated"))
    assert not _is_unreachable_bad_request(FakeTelegramError("Bad Request: can't parse entities"))


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
    assert all(word not in report.casefold() for word in ("mutaxassis", "murojaat", "shoshilinch yordam"))


def test_reverse_scored_wellbeing_item_uses_four_option_scale():
    question = Question(
        id=4,
        category_slug="wellbeing",
        age_band="31-50",
        prompt_uz="So‘nggi ikki hafta ichida dam olishga vaqt ajratish qiyin bo‘ldi.",
        options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha"],
        factor="energy",
        reverse_scored=True,
    )
    score, maximum, _report = score_answers("wellbeing", [question], [0])
    assert (score, maximum) == (3, 3)


def test_personality_report_is_detailed_and_reflects_all_five_dimensions():
    bank = [
        item
        for item in build_question_bank()
        if item.category_slug == "personality" and item.age_band == "18-30"
    ]
    questions = [
        Question(
            id=index,
            category_slug=item.category_slug,
            age_band=item.age_band,
            prompt_uz=item.prompt_uz,
            options_uz=item.options_uz,
            factor=item.factor,
            reverse_scored=item.reverse_scored,
        )
        for index, item in enumerate(bank, start=1)
    ]

    score, maximum, report = score_answers("personality", questions, [3] * len(questions))

    assert maximum == 100
    assert 0 <= score <= maximum
    assert len(report) > 1800
    assert "Qiziquvchanlik va yangi g‘oyalar" in report
    assert "Hissiy muvozanat va moslashuv" in report


def test_wellbeing_questions_are_time_bounded_and_report_is_detailed_without_referrals():
    bank = [
        item
        for item in build_question_bank()
        if item.category_slug == "wellbeing" and item.age_band == "18-30"
    ]
    assert len(bank) == 20
    assert all(item.prompt_uz.startswith("So‘nggi ikki hafta ichida ") for item in bank)
    assert {item.factor for item in bank} == {
        "energy",
        "interest",
        "self_awareness",
        "daily_routine",
        "connection",
    }
    questions = [
        Question(
            id=index,
            category_slug=item.category_slug,
            age_band=item.age_band,
            prompt_uz=item.prompt_uz,
            options_uz=item.options_uz,
            factor=item.factor,
            reverse_scored=item.reverse_scored,
        )
        for index, item in enumerate(bank, start=1)
    ]

    score, maximum, report = score_answers("wellbeing", questions, [2] * len(questions))

    assert (score, maximum) == (35, 60)
    assert len(report) > 1800
    assert "Quvvat va dam olish" in report
    assert "Kichik tajriba" in report
    assert all(word not in report.casefold() for word in ("mutaxassis", "murojaat", "shoshilinch yordam"))


def test_professional_question_set_has_twenty_distinct_items_per_personality_dimension():
    bank = [
        item
        for item in build_question_bank()
        if item.category_slug == "personality" and item.age_band == "18-30"
    ]
    assert len(bank) == 20
    assert len({item.prompt_uz for item in bank}) == 20
    assert {factor: sum(item.factor == factor for item in bank) for factor in {item.factor for item in bank}} == {
        "curiosity": 4,
        "reliability": 4,
        "sociability": 4,
        "kindness": 4,
        "calmness": 4,
    }
    assert all(item.prompt_uz.startswith("Odatda, ") for item in bank)


def test_iq_bank_has_one_hundred_distinct_multi_step_items_per_age_band():
    bank = build_question_bank()
    for _minimum, _maximum, age_band in AGE_BANDS:
        questions = [
            item for item in bank if item.category_slug == "iq" and item.age_band == age_band
        ]
        prompts = {item.prompt_uz for item in questions}
        assert len(questions) == IQ_QUESTION_BANK_SIZE == 100
        assert len(prompts) == IQ_QUESTION_BANK_SIZE
        assert all(
            len(item.options_uz) == 4
            and len(set(item.options_uz)) == 4
            and item.correct_index is not None
            and 0 <= item.correct_index < 4
            for item in questions
        )
        assert any("farqlar jadvali" in item.prompt_uz for item in questions)
        assert any("ikki xil amal navbatma-navbat" in item.prompt_uz for item in questions)
        assert any("mustaqil qonuniyat navbatma-navbat" in item.prompt_uz for item in questions)
        assert any("yashirin qoida" in item.prompt_uz for item in questions)
