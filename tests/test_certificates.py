from datetime import datetime, timezone

import pytest

from mindora.certificates import build_iq_completion_certificate
from mindora.handlers import report_delivery_data, send_released_report
from mindora.models import AssessmentReport, TestAttempt as AttemptModel, User


def test_iq_completion_certificate_builds_unicode_pdf():
    pdf = build_iq_completion_certificate(
        first_name="G‘ulom",
        last_name="O‘g‘li",
        age=17,
        score=29,
        max_score=35,
        completed_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 10_000


@pytest.mark.parametrize(
    "values",
    [
        {"first_name": "", "last_name": None, "age": 18, "score": 20, "max_score": 35},
        {"first_name": "Test", "last_name": None, "age": 6, "score": 20, "max_score": 35},
        {"first_name": "Test", "last_name": None, "age": 18, "score": 36, "max_score": 35},
    ],
)
def test_iq_certificate_rejects_incomplete_or_invalid_data(values):
    with pytest.raises(ValueError):
        build_iq_completion_certificate(**values, completed_at=None)


def test_certificate_uses_registered_names_and_age_at_test():
    user = User(first_name="G‘ulom", last_name="O‘g‘li", age=18)
    attempt = AttemptModel(
        category_slug="iq",
        age_at_test=17,
        score=29,
        max_score=35,
        completed_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    report = AssessmentReport(id=42, report_text="Analysis")

    data = report_delivery_data(report, user, attempt)

    assert data["first_name"] == "G‘ulom"
    assert data["last_name"] == "O‘g‘li"
    assert data["age"] == 17


@pytest.mark.asyncio
async def test_iq_report_is_pdf_and_other_assessments_are_text():
    class RecordingBot:
        def __init__(self):
            self.documents = []
            self.messages = []

        async def send_document(self, chat_id, document, caption):
            self.documents.append((chat_id, document, caption))

        async def send_message(self, chat_id, text):
            self.messages.append((chat_id, text))

    bot = RecordingBot()
    iq_data = {
        "category_slug": "iq",
        "report_id": 42,
        "report_text": "Not shown as a text report.",
        "first_name": "G‘ulom",
        "last_name": "O‘g‘li",
        "age": 17,
        "score": 29,
        "max_score": 35,
        "completed_at": datetime(2026, 10, 20, tzinfo=timezone.utc),
    }
    await send_released_report(bot, 123, iq_data)
    assert len(bot.documents) == 1
    assert bot.documents[0][0] == 123
    assert bot.documents[0][1].filename.endswith(".pdf")
    assert not bot.messages

    await send_released_report(
        bot,
        123,
        {**iq_data, "category_slug": "personality", "report_text": "Tahlil matni"},
    )
    assert bot.messages == [(123, "To‘lov tasdiqlandi. Hisobotingiz:\n\nTahlil matni")]
