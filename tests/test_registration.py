from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mindora.handlers import cancel_command, start_command
from mindora.models import ConversationState, User
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
            first_name="Telegram",
            last_name=None,
        )
        session.add(
            ConversationState(
                telegram_id=telegram_id,
                state="awaiting_age",
                payload={"first_name": "Test", "last_name": "User"},
            )
        )

    class FakeMessage:
        from_user = SimpleNamespace(id=telegram_id)
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.responses = []

        async def answer(self, text, **_kwargs):
            self.responses.append(text)

    message = FakeMessage()
    await cancel_command(message)

    async with factory() as session:
        state = await session.get(ConversationState, telegram_id)
    assert state is not None
    assert state.state == "awaiting_first_name"
    assert any("ismingizni kiriting" in response.casefold() for response in message.responses)


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
