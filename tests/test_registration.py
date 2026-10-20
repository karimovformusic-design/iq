from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mindora.handlers import cancel_command, start_command, user_callback
from mindora.keyboards import user_main_menu
from mindora.models import (
    AssessmentReport,
    ConversationState,
    Payment,
    TestAttempt as Attempt,
    TestCategory as Category,
    User,
)
from mindora.registration import normalize_registration_name, parse_registration_age
from mindora.services import upsert_user


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


@pytest.mark.asyncio
async def test_cancel_during_registration_restarts_at_first_name(db_session, monkeypatch):
    telegram_id = 912233443
    factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr("mindora.handlers.SessionFactory", factory)
    async with factory() as session, session.begin():
        await upsert_user(
            session,
            telegram_id=telegram_id,
            username=None,
            first_name="Test",
            last_name="User",
            age=25,
        )
        session.add(
            ConversationState(
                telegram_id=telegram_id,
                state="awaiting_age",
                payload={"first_name": "Test", "last_name": "User"},
            )
        )

    class FakeMessage:
        from_user = SimpleNamespace(id=telegram_id, username=None)
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.responses = []

        async def answer(self, text, **_kwargs):
            self.responses.append(text)

    message = FakeMessage()
    await cancel_command(message)

    async with factory() as session:
        state = await session.get(ConversationState, telegram_id)
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    assert state is not None
    assert state.state == "awaiting_first_name"
    assert user is not None
    assert (user.first_name, user.last_name, user.age, user.registration_completed) == (
        "",
        None,
        None,
        False,
    )
    assert any("ismingizni kiriting" in response.casefold() for response in message.responses)


@pytest.mark.asyncio
async def test_cancel_resets_profile_but_preserves_test_and_payment_history(db_session, monkeypatch):
    telegram_id = 912233445
    factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr("mindora.handlers.SessionFactory", factory)
    async with factory() as session, session.begin():
        user = await upsert_user(
            session,
            telegram_id=telegram_id,
            username="history_user",
            first_name="Old",
            last_name="Name",
            age=25,
        )
        category = Category(
            slug="iq",
            name_uz="IQ",
            description_uz="Test category",
            sort_order=0,
        )
        session.add(category)
        await session.flush()
        attempt = Attempt(
            user_id=user.id,
            category_slug=category.slug,
            age_at_test=25,
            age_band="18-30",
            question_order=[],
            answered_count=20,
            status="completed",
            score=15,
            max_score=20,
        )
        session.add(attempt)
        await session.flush()
        report = AssessmentReport(
            attempt_id=attempt.id,
            user_id=user.id,
            report_text="Existing analysis",
            released_to_user=True,
        )
        session.add(report)
        await session.flush()
        payment = Payment(
            user_id=user.id,
            report_id=report.id,
            amount_uzs=11900,
            status="approved",
            receipt_file_id="test-file-id",
            receipt_file_unique_id="test-file-unique-id",
            receipt_kind="photo",
        )
        session.add(payment)
        await session.flush()
        attempt_id, report_id, payment_id = attempt.id, report.id, payment.id

    class FakeMessage:
        from_user = SimpleNamespace(id=telegram_id, username="history_user")
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.responses = []

        async def answer(self, text, **_kwargs):
            self.responses.append(text)

    message = FakeMessage()
    await cancel_command(message)

    async with factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        state = await session.get(ConversationState, telegram_id)
        attempt = await session.get(Attempt, attempt_id)
        report = await session.get(AssessmentReport, report_id)
        payment = await session.get(Payment, payment_id)
    assert user is not None
    assert (user.first_name, user.last_name, user.age, user.registration_completed) == (
        "",
        None,
        None,
        False,
    )
    assert state is not None and state.state == "awaiting_first_name"
    assert attempt is not None
    assert report is not None
    assert payment is not None and payment.status == "approved"
    assert "to‘lov tarixi saqlanadi" in message.responses[0]


@pytest.mark.asyncio
async def test_main_menu_cancel_button_restarts_registration(db_session, monkeypatch):
    telegram_id = 912233447
    factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr("mindora.handlers.SessionFactory", factory)
    async with factory() as session, session.begin():
        await upsert_user(
            session,
            telegram_id=telegram_id,
            username="button_user",
            first_name="Old",
            last_name="Name",
            age=31,
        )

    buttons = [
        button
        for row in user_main_menu(False).inline_keyboard
        for button in row
    ]
    assert any(
        button.callback_data == "user:cancel-current"
        and button.text == "❌ Joriy amalni bekor qilish"
        for button in buttons
    )

    class FakeCallbackMessage:
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.text = None

        async def edit_text(self, text, **_kwargs):
            self.text = text

    class FakeCallback:
        data = "user:cancel-current"
        from_user = SimpleNamespace(id=telegram_id, username="button_user")

        def __init__(self):
            self.message = FakeCallbackMessage()

        async def answer(self, *_args, **_kwargs):
            return None

    callback = FakeCallback()
    await user_callback(callback)

    async with factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        state = await session.get(ConversationState, telegram_id)
    assert user is not None
    assert (user.first_name, user.last_name, user.age, user.registration_completed) == (
        "",
        None,
        None,
        False,
    )
    assert state is not None and state.state == "awaiting_first_name"
    assert "Qayta ro‘yxatdan o‘tish" in callback.message.text


@pytest.mark.asyncio
async def test_cancel_in_admin_workflow_does_not_reset_admin_profile(db_session, monkeypatch):
    telegram_id = 912233446
    factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr("mindora.handlers.SessionFactory", factory)
    monkeypatch.setattr(
        "mindora.handlers.is_authorized_admin",
        lambda user_id, _admin_ids: user_id == telegram_id,
    )
    async with factory() as session, session.begin():
        await upsert_user(
            session,
            telegram_id=telegram_id,
            username="admin_user",
            first_name="Admin",
            last_name="User",
            age=30,
        )
        session.add(
            ConversationState(
                telegram_id=telegram_id,
                state="admin_broadcast_message",
                payload={},
            )
        )

    class FakeMessage:
        from_user = SimpleNamespace(id=telegram_id, username="admin_user")
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.responses = []

        async def answer(self, text, **kwargs):
            self.responses.append((text, kwargs))

    message = FakeMessage()
    await cancel_command(message)

    async with factory() as session:
        state = await session.get(ConversationState, telegram_id)
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    assert state is None
    assert user is not None
    assert (user.first_name, user.last_name, user.age, user.registration_completed) == (
        "Admin",
        "User",
        30,
        True,
    )
    assert "administrator amali bekor qilindi" in message.responses[0][0].casefold()


@pytest.mark.asyncio
async def test_every_start_reopens_registration_without_deleting_profile(db_session, monkeypatch):
    telegram_id = 912233444
    factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr("mindora.handlers.SessionFactory", factory)
    async with factory() as session, session.begin():
        user = await upsert_user(
            session,
            telegram_id=telegram_id,
            username="old_user",
            first_name="Old",
            last_name="Name",
            age=25,
        )
        assert user.registration_completed is True

    class FakeMessage:
        from_user = SimpleNamespace(
            id=telegram_id,
            username="old_user",
            first_name="Telegram",
            last_name="Changed",
        )
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.responses = []

        async def answer(self, text, **_kwargs):
            self.responses.append(text)

    message = FakeMessage()
    await start_command(message)

    async with factory() as session:
        state = await session.get(ConversationState, telegram_id)
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    assert state is not None and state.state == "awaiting_first_name"
    assert user.registration_completed is False
    assert (user.first_name, user.last_name, user.age) == ("Old", "Name", 25)
    assert any("ismingizni kiriting" in response.casefold() for response in message.responses)
