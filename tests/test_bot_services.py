import random

import pytest
from sqlalchemy import func, select

from mindora.constants import PRICE_PER_REPORT_UZS
from mindora.models import (
    AdminAction,
    BroadcastJob,
    BroadcastRecipient,
    NotificationPreference,
    Question,
    TestAnswer as AnswerModel,
    User,
)
from mindora.seed import seed_database
from mindora.services import (
    approve_payment,
    broadcast_stats,
    create_broadcast_job,
    dashboard_stats,
    get_report_for_user,
    list_users,
    reject_payment,
    record_answer,
    start_attempt,
    set_user_status,
    submit_receipt,
    upsert_user,
)


async def _registered_user(session, telegram_id: int, age: int = 18, **kwargs) -> User:
    user = await upsert_user(
        session,
        telegram_id=telegram_id,
        username=kwargs.get("username"),
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name"),
        age=age,
    )
    await session.flush()
    return user


async def _completed_attempt(session, telegram_id: int = 112233445):
    await seed_database(session)
    await session.flush()
    user = await _registered_user(session, telegram_id, age=18)
    attempt = await start_attempt(
        session,
        telegram_id=telegram_id,
        category_slug="iq",
        sampler=random.Random(22),
    )
    question_ids = list(attempt.question_order)
    questions = list(await session.scalars(select(Question).where(Question.id.in_(question_ids))))
    by_id = {question.id: question for question in questions}
    report = None
    for position, question_id in enumerate(question_ids):
        question = by_id[question_id]
        final, report = await record_answer(
            session,
            attempt_id=attempt.id,
            telegram_id=telegram_id,
            position=position,
            answer_index=question.correct_index,
        )
    assert final and report is not None
    await session.flush()
    return user, attempt, report


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_questions_are_age_banded(db_session):
    first = await seed_database(db_session)
    second = await seed_database(db_session)
    await db_session.flush()
    assert first == 325
    assert second == 0

    user = await _registered_user(db_session, 912233441, age=70)
    attempt = await start_attempt(
        db_session,
        telegram_id=user.telegram_id,
        category_slug="personality",
        sampler=random.Random(3),
    )
    assert attempt.age_band == "51-70"
    assert len(attempt.question_order) == 10
    assert len(set(attempt.question_order)) == 10


@pytest.mark.asyncio
async def test_age_validation_prevents_invalid_registration(db_session):
    with pytest.raises(ValueError):
        await upsert_user(
            db_session,
            telegram_id=1,
            username=None,
            first_name="Invalid",
            last_name=None,
            age=6,
        )


@pytest.mark.asyncio
async def test_answer_flow_completes_once_and_report_is_private(db_session):
    user, attempt, report = await _completed_attempt(db_session, 112233445)
    assert attempt.status == "completed"
    assert attempt.answered_count == 10
    assert report.released_to_user is False
    assert await db_session.scalar(
        select(func.count(AnswerModel.id)).where(AnswerModel.attempt_id == attempt.id)
    ) == 10
    assert await get_report_for_user(
        db_session,
        report_id=report.id,
        telegram_id=user.telegram_id,
    ) is not None
    assert await get_report_for_user(
        db_session,
        report_id=report.id,
        telegram_id=user.telegram_id + 1,
    ) is None

    with pytest.raises(ValueError):
        await record_answer(
            db_session,
            attempt_id=attempt.id,
            telegram_id=user.telegram_id,
            position=9,
            answer_index=0,
        )


@pytest.mark.asyncio
async def test_receipt_submission_and_payment_approval_are_idempotent(db_session):
    user, attempt, report = await _completed_attempt(db_session)
    payment = await submit_receipt(
        db_session,
        telegram_id=user.telegram_id,
        report_id=report.id,
        file_id="telegram-file-id",
        file_unique_id="unique-receipt-id",
        receipt_kind="photo",
    )
    assert payment.amount_uzs == PRICE_PER_REPORT_UZS
    assert payment.status == "pending"
    duplicate = await submit_receipt(
        db_session,
        telegram_id=user.telegram_id,
        report_id=report.id,
        file_id="telegram-file-id",
        file_unique_id="unique-receipt-id",
        receipt_kind="photo",
    )
    assert duplicate.id == payment.id

    approved, changed = await approve_payment(
        db_session,
        payment_id=payment.id,
        admin_telegram_id=998877665,
    )
    assert approved.status == "approved"
    assert changed is True
    assert report.released_to_user is True
    same_payment, changed_again = await approve_payment(
        db_session,
        payment_id=payment.id,
        admin_telegram_id=998877665,
    )
    assert same_payment.status == "approved"
    assert changed_again is False
    assert await db_session.scalar(select(func.count(AdminAction.id))) == 1


@pytest.mark.asyncio
async def test_payment_rejection_is_audited_and_does_not_release_report(db_session):
    user, _attempt, report = await _completed_attempt(db_session, telegram_id=112233446)
    payment = await submit_receipt(
        db_session,
        telegram_id=user.telegram_id,
        report_id=report.id,
        file_id="rejected-file",
        file_unique_id="rejected-unique-id",
        receipt_kind="photo",
    )

    rejected = await reject_payment(
        db_session,
        payment_id=payment.id,
        admin_telegram_id=998877665,
        reason="Chekdagi summa mos kelmadi.",
    )
    assert rejected.status == "rejected"
    assert rejected.reviewed_by_telegram_id == 998877665
    assert report.released_to_user is False
    action = await db_session.scalar(select(AdminAction).where(AdminAction.action == "payment_rejected"))
    assert action is not None
    assert action.actor_telegram_id == 998877665
    assert action.target_user_id == user.id
    assert action.reason == "Chekdagi summa mos kelmadi."
    with pytest.raises(ValueError):
        await reject_payment(
            db_session,
            payment_id=payment.id,
            admin_telegram_id=998877665,
            reason="Takroriy rad etish",
        )


@pytest.mark.asyncio
async def test_dashboard_and_directory_are_database_backed(db_session):
    await _completed_attempt(db_session, 123456001)
    await _registered_user(
        db_session,
        123456002,
        age=30,
        username="lookup_person",
        first_name="Karim",
        last_name="Test",
    )
    stats = await dashboard_stats(db_session)
    assert stats["total_users"] == 2
    assert stats["completed_tests"] == 1
    assert stats["iq_completed"] == 1

    matches, total = await list_users(
        db_session,
        page=0,
        page_size=10,
        search_term="lookup_person",
    )
    assert total == 1
    assert matches[0]["user"].telegram_id == 123456002


@pytest.mark.asyncio
async def test_user_directory_paginates_and_moderation_is_audited(db_session):
    users = [
        await _registered_user(
            db_session,
            telegram_id=223344500 + index,
            username=f"directory_{index}",
            first_name=f"Directory {index}",
        )
        for index in range(11)
    ]
    first_page, total = await list_users(db_session, page=0, page_size=10)
    second_page, second_total = await list_users(db_session, page=1, page_size=10)
    assert total == second_total == 11
    assert len(first_page) == 10
    assert len(second_page) == 1

    target = users[0]
    suspended = await set_user_status(
        db_session,
        user_id=target.id,
        admin_telegram_id=998877665,
        status="suspended",
        reason="Foydalanish qoidalarini buzgan.",
    )
    assert suspended.account_status == "suspended"
    reactivated = await set_user_status(
        db_session,
        user_id=target.id,
        admin_telegram_id=998877665,
        status="active",
        reason="Tekshiruvdan so‘ng faollashtirildi.",
    )
    assert reactivated.account_status == "active"
    actions = list(
        await db_session.scalars(
            select(AdminAction).where(
                AdminAction.target_user_id == target.id,
                AdminAction.action.in_(["account_suspended", "account_active"]),
            )
        )
    )
    assert {action.actor_telegram_id for action in actions} == {998877665}
    assert len(actions) == 2


@pytest.mark.asyncio
async def test_broadcast_snapshots_only_eligible_users(db_session):
    user_a = await _registered_user(db_session, 456001001)
    user_b = await _registered_user(db_session, 456001002)
    user_c = await _registered_user(db_session, 456001003)
    user_b.account_status = "suspended"
    pref_a = await db_session.get(NotificationPreference, user_a.id)
    pref_b = await db_session.get(NotificationPreference, user_b.id)
    pref_c = await db_session.get(NotificationPreference, user_c.id)
    pref_a.promotional_opt_in = True
    pref_c.promotional_opt_in = True
    pref_c.bot_blocked = True

    job, eligible = await create_broadcast_job(
        db_session,
        audience="promotional",
        message_text="Salom, test xabari!",
        photo_file_id=None,
        entities_json=None,
        caption_entities_json=None,
        initiated_by_telegram_id=998877665,
    )
    assert eligible == 1
    recipients = list(
        await db_session.scalars(
            select(BroadcastRecipient).where(BroadcastRecipient.job_id == job.id)
        )
    )
    assert len(recipients) == 1
    stats = await broadcast_stats(db_session, job.id)
    assert stats == {
        "job_id": job.id,
        "status": "queued",
        "total": 1,
        "sent": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
        "remaining": 1,
    }

    service_job, service_eligible = await create_broadcast_job(
        db_session,
        audience="service",
        message_text="Xizmat e’loni",
        photo_file_id=None,
        entities_json=None,
        caption_entities_json=None,
        initiated_by_telegram_id=998877665,
    )
    assert service_eligible == 1
    assert service_job.status == "queued"


@pytest.mark.asyncio
async def test_empty_broadcast_completes_without_waiting_for_worker(db_session):
    job, eligible = await create_broadcast_job(
        db_session,
        audience="promotional",
        message_text="Taklif",
        photo_file_id=None,
        entities_json=None,
        caption_entities_json=None,
        initiated_by_telegram_id=998877665,
    )
    assert eligible == 0
    assert job.status == "completed"
    stats = await broadcast_stats(db_session, job.id)
    assert stats["remaining"] == 0


@pytest.mark.asyncio
async def test_restart_recovery_never_replays_an_interrupted_delivery(db_session, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from mindora import broadcast_worker

    user = await _registered_user(db_session, 456002001)
    pending_user = await _registered_user(db_session, 456002002)
    job = BroadcastJob(
        status="running",
        audience="service",
        message_text="Xizmat xabari",
        initiated_by_telegram_id=998877665,
    )
    db_session.add(job)
    await db_session.flush()
    sending = BroadcastRecipient(job_id=job.id, user_id=user.id, status="sending", attempts=1)
    pending = BroadcastRecipient(job_id=job.id, user_id=pending_user.id, status="pending", attempts=0)
    db_session.add_all([sending, pending])
    await db_session.flush()
    sending_id = sending.id
    pending_id = pending.id
    await db_session.commit()

    test_factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr(broadcast_worker, "SessionFactory", test_factory)

    class NoNetworkBot:
        async def send_message(self, *_args, **_kwargs):
            raise AssertionError("Restart recovery must not send messages.")

    recovered = await broadcast_worker.recover_interrupted_deliveries(NoNetworkBot())
    assert recovered == 1
    sending_after_restart = await db_session.get(BroadcastRecipient, sending_id)
    pending_after_restart = await db_session.get(BroadcastRecipient, pending_id)
    await db_session.refresh(sending_after_restart)
    await db_session.refresh(pending_after_restart)
    assert sending_after_restart.status == "failed"
    assert sending_after_restart.result_code == "uncertain_after_restart"
    assert pending_after_restart.status == "pending"


@pytest.mark.asyncio
async def test_worker_skips_user_who_opts_out_after_broadcast_confirmation(db_session, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from mindora import broadcast_worker

    user = await _registered_user(db_session, 456002003)
    preference = await db_session.get(NotificationPreference, user.id)
    preference.service_opt_in = False
    job = BroadcastJob(
        status="queued",
        audience="service",
        message_text="Xizmat e’loni",
        initiated_by_telegram_id=998877665,
    )
    db_session.add(job)
    await db_session.flush()
    recipient = BroadcastRecipient(job_id=job.id, user_id=user.id, status="pending", attempts=0)
    db_session.add(recipient)
    await db_session.flush()
    recipient_id = recipient.id
    job_id = job.id
    await db_session.commit()

    test_factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr(broadcast_worker, "SessionFactory", test_factory)

    class RecordingBot:
        def __init__(self):
            self.messages = []

        async def send_message(self, chat_id, text, **_kwargs):
            self.messages.append((chat_id, text))

    bot = RecordingBot()
    worked = await broadcast_worker._send_one(bot)
    assert worked
    recipient_after = await db_session.get(BroadcastRecipient, recipient_id)
    await db_session.refresh(recipient_after)
    assert recipient_after.status == "skipped"
    assert all(chat_id != user.telegram_id for chat_id, _ in bot.messages)
    assert len(bot.messages) == 1
    assert bot.messages[0][0] == 998877665
    job_after = await db_session.get(BroadcastJob, job_id)
    await db_session.refresh(job_after)
    stats = await broadcast_stats(db_session, job_id)
    assert stats["status"] == "completed"
    assert stats["skipped"] == 1
    assert stats["remaining"] == 0


@pytest.mark.asyncio
async def test_worker_tracks_successful_broadcast_delivery(db_session, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from mindora import broadcast_worker

    user = await _registered_user(db_session, 456002004)
    job = BroadcastJob(
        status="queued",
        audience="service",
        message_text="Muhim xizmat e’loni",
        initiated_by_telegram_id=998877665,
    )
    db_session.add(job)
    await db_session.flush()
    recipient = BroadcastRecipient(job_id=job.id, user_id=user.id, status="pending", attempts=0)
    db_session.add(recipient)
    await db_session.flush()
    recipient_id = recipient.id
    job_id = job.id
    await db_session.commit()

    test_factory = async_sessionmaker(
        db_session.info["test_async_engine"],
        expire_on_commit=False,
    )
    monkeypatch.setattr(broadcast_worker, "SessionFactory", test_factory)

    class RecordingBot:
        def __init__(self):
            self.messages = []

        async def send_message(self, chat_id, text, **_kwargs):
            self.messages.append((chat_id, text))

    bot = RecordingBot()
    assert await broadcast_worker._send_one(bot)
    recipient_after = await db_session.get(BroadcastRecipient, recipient_id)
    await db_session.refresh(recipient_after)
    assert recipient_after.status == "sent"
    assert any(
        chat_id == user.telegram_id and text == "Muhim xizmat e’loni"
        for chat_id, text in bot.messages
    )
    assert any(chat_id == 998877665 and "yakunlandi" in text for chat_id, text in bot.messages)
    job_after = await db_session.get(BroadcastJob, job_id)
    await db_session.refresh(job_after)
    stats = await broadcast_stats(db_session, job_id)
    assert stats["status"] == "completed"
    assert stats["sent"] == 1
    assert stats["failed"] == 0
    assert stats["remaining"] == 0
