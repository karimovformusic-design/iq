from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mindora.constants import (
    PRICE_PER_REPORT_UZS,
    QUESTION_COUNT_PER_ATTEMPT,
    TEST_NAMES,
    age_band_for,
)
from mindora.models import (
    AdminAction,
    AssessmentReport,
    BotSetting,
    BroadcastJob,
    BroadcastRecipient,
    ConversationState,
    NotificationPreference,
    Payment,
    Question,
    TestAnswer,
    TestAttempt,
    TestCategory,
    User,
)
from mindora.scoring import score_answers


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str,
    last_name: str | None,
    age: int | None = None,
) -> User:
    if age is not None and not 7 <= age <= 70:
        raise ValueError("Yosh 7 dan 70 gacha bo‘lishi kerak.")
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id).with_for_update())
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=(username or "").lstrip("@") or None,
            first_name=first_name[:128],
            last_name=(last_name or None),
            age=age,
        )
        session.add(user)
        await session.flush()
        session.add(NotificationPreference(user_id=user.id))
    else:
        user.username = (username or "").lstrip("@") or None
        user.first_name = first_name[:128]
        user.last_name = last_name or None
        user.last_active_at = utc_now()
        if age is not None:
            user.age = age
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_report_for_user(
    session: AsyncSession,
    *,
    report_id: int,
    telegram_id: int,
) -> tuple[AssessmentReport, User] | None:
    row = await session.execute(
        select(AssessmentReport, User)
        .join(User, User.id == AssessmentReport.user_id)
        .where(AssessmentReport.id == report_id, User.telegram_id == telegram_id)
    )
    return row.one_or_none()


async def start_attempt(
    session: AsyncSession,
    *,
    telegram_id: int,
    category_slug: str,
    sampler: Any = random.SystemRandom(),
) -> TestAttempt:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None or user.age is None:
        raise ValueError("Avval ro‘yxatdan o‘tib, yoshingizni kiriting.")
    if user.account_status != "active":
        raise PermissionError("Hisobingiz vaqtincha to‘xtatilgan. Yordam uchun administratorga yozing.")
    category = await session.get(TestCategory, category_slug)
    if category is None or not category.is_enabled:
        raise ValueError("Bu test hozircha mavjud emas.")

    age_band = age_band_for(user.age)
    available = list(
        await session.scalars(
            select(Question)
            .where(
                Question.category_slug == category_slug,
                Question.age_band == age_band,
                Question.is_active.is_(True),
            )
        )
    )
    if len(available) < QUESTION_COUNT_PER_ATTEMPT:
        raise RuntimeError("Savollar yetarli emas. Administratorga xabar bering.")
    selected = sampler.sample(available, QUESTION_COUNT_PER_ATTEMPT)

    await session.execute(
        update(TestAttempt)
        .where(TestAttempt.user_id == user.id, TestAttempt.status == "in_progress")
        .values(status="abandoned")
    )
    attempt = TestAttempt(
        user_id=user.id,
        category_slug=category_slug,
        age_at_test=user.age,
        age_band=age_band,
        question_order=[question.id for question in selected],
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def question_for_attempt_position(
    session: AsyncSession,
    *,
    attempt_id: int,
    telegram_id: int,
    position: int,
) -> tuple[TestAttempt, Question] | None:
    attempt = await session.scalar(
        select(TestAttempt)
        .join(User, User.id == TestAttempt.user_id)
        .where(TestAttempt.id == attempt_id, User.telegram_id == telegram_id)
    )
    if (
        attempt is None
        or attempt.status != "in_progress"
        or position < 0
        or position >= len(attempt.question_order)
        or position != attempt.answered_count
    ):
        return None
    question = await session.get(Question, attempt.question_order[position])
    return (attempt, question) if question is not None else None


async def record_answer(
    session: AsyncSession,
    *,
    attempt_id: int,
    telegram_id: int,
    position: int,
    answer_index: int,
) -> tuple[bool, AssessmentReport | None]:
    attempt = await session.scalar(
        select(TestAttempt)
        .join(User, User.id == TestAttempt.user_id)
        .where(TestAttempt.id == attempt_id, User.telegram_id == telegram_id)
        .with_for_update()
    )
    if attempt is None or attempt.status != "in_progress":
        raise ValueError("Bu test topilmadi yoki yakunlangan.")
    if position != attempt.answered_count or position < 0 or position >= len(attempt.question_order):
        raise ValueError("Bu savolga javob allaqachon yuborilgan yoki test ketma-ketligi noto‘g‘ri.")
    question_id = attempt.question_order[position]
    question = await session.get(Question, question_id)
    if question is None or answer_index < 0 or answer_index >= len(question.options_uz):
        raise ValueError("Javob varianti noto‘g‘ri.")

    is_correct = answer_index == question.correct_index if question.correct_index is not None else None
    if is_correct is not None:
        score_value = int(is_correct)
    elif question.category_slug == "personality" and question.reverse_scored:
        score_value = 4 - answer_index
    else:
        score_value = answer_index
    session.add(
        TestAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_index=answer_index,
            is_correct=is_correct,
            score_value=score_value,
        )
    )
    attempt.answered_count += 1
    if attempt.answered_count < len(attempt.question_order):
        return False, None

    questions = list(
        await session.scalars(select(Question).where(Question.id.in_(attempt.question_order)))
    )
    question_map = {question.id: question for question in questions}
    ordered_questions = [question_map[question_id] for question_id in attempt.question_order]
    answers = list(
        await session.scalars(
            select(TestAnswer.answer_index)
            .where(TestAnswer.attempt_id == attempt.id)
            .order_by(TestAnswer.id)
        )
    )
    score, maximum, report_text = score_answers(attempt.category_slug, ordered_questions, answers)
    attempt.status = "completed"
    attempt.score = score
    attempt.max_score = maximum
    attempt.completed_at = utc_now()
    report = AssessmentReport(
        attempt_id=attempt.id,
        user_id=attempt.user_id,
        report_text=report_text,
    )
    session.add(report)
    await session.flush()
    return True, report


async def delete_completed_attempt_data(
    session: AsyncSession,
    *,
    telegram_id: int,
    report_id: int,
) -> bool:
    row = await session.execute(
        select(AssessmentReport, TestAttempt)
        .join(TestAttempt, TestAttempt.id == AssessmentReport.attempt_id)
        .join(User, User.id == AssessmentReport.user_id)
        .where(AssessmentReport.id == report_id, User.telegram_id == telegram_id)
        .with_for_update()
    )
    owned = row.one_or_none()
    if owned is None:
        return False
    report, attempt = owned
    if attempt.status != "completed":
        return False
    if report.released_to_user:
        raise ValueError("To‘lov tasdiqlangan hisobotni o‘chirib bo‘lmaydi.")
    payment_id = await session.scalar(
        select(Payment.id).where(Payment.report_id == report.id).limit(1).with_for_update()
    )
    if payment_id is not None:
        raise ValueError("Chek yuborilgan hisobotni o‘chirib bo‘lmaydi.")

    await session.execute(delete(TestAnswer).where(TestAnswer.attempt_id == attempt.id))
    state = await session.get(ConversationState, telegram_id)
    if (
        state is not None
        and state.state == "awaiting_receipt"
        and (state.payload or {}).get("report_id") == report.id
    ):
        await session.delete(state)
    await session.delete(report)
    attempt.status = "abandoned"
    attempt.answered_count = 0
    attempt.score = None
    attempt.max_score = None
    attempt.completed_at = None
    await session.flush()
    return True


async def submit_receipt(
    session: AsyncSession,
    *,
    telegram_id: int,
    report_id: int,
    file_id: str,
    file_unique_id: str,
    receipt_kind: str,
) -> Payment:
    owned = await get_report_for_user(session, report_id=report_id, telegram_id=telegram_id)
    if owned is None:
        raise ValueError("Hisobot topilmadi.")
    report, user = owned
    if report.released_to_user:
        raise ValueError("Bu hisobot uchun to‘lov allaqachon tasdiqlangan.")

    duplicate = await session.scalar(
        select(Payment).where(Payment.receipt_file_unique_id == file_unique_id)
    )
    if duplicate is not None:
        if duplicate.user_id == user.id and duplicate.report_id == report.id:
            return duplicate
        raise ValueError("Bu chek avval boshqa to‘lov uchun yuborilgan.")

    pending = await session.scalar(
        select(Payment)
        .where(Payment.report_id == report.id, Payment.status == "pending")
        .with_for_update()
    )
    if pending is not None:
        pending.receipt_file_id = file_id
        pending.receipt_file_unique_id = file_unique_id
        pending.receipt_kind = receipt_kind
        pending.submitted_at = utc_now()
        return pending

    try:
        async with session.begin_nested():
            payment = Payment(
                user_id=user.id,
                report_id=report.id,
                amount_uzs=PRICE_PER_REPORT_UZS,
                status="pending",
                receipt_file_id=file_id,
                receipt_file_unique_id=file_unique_id,
                receipt_kind=receipt_kind,
            )
            session.add(payment)
            await session.flush()
    except IntegrityError:
        existing = await session.scalar(
            select(Payment).where(Payment.report_id == report.id, Payment.status == "pending")
        )
        if existing is None:
            raise
        return existing
    return payment


async def approve_payment(
    session: AsyncSession,
    *,
    payment_id: int,
    admin_telegram_id: int,
) -> tuple[Payment, bool]:
    payment = await session.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
    if payment is None:
        raise ValueError("To‘lov topilmadi.")
    if payment.status == "approved":
        return payment, False
    if payment.status != "pending":
        raise ValueError("Faqat kutilayotgan to‘lovni tasdiqlash mumkin.")

    report = await session.scalar(
        select(AssessmentReport).where(AssessmentReport.id == payment.report_id).with_for_update()
    )
    if report is None:
        raise ValueError("Hisobot topilmadi.")
    if report.released_to_user:
        payment.status = "approved"
        payment.reviewed_at = utc_now()
        payment.reviewed_by_telegram_id = admin_telegram_id
        return payment, False

    payment.status = "approved"
    payment.reviewed_at = utc_now()
    payment.reviewed_by_telegram_id = admin_telegram_id
    report.released_to_user = True
    session.add(
        AdminAction(
            actor_telegram_id=admin_telegram_id,
            target_user_id=payment.user_id,
            action="payment_approved",
            metadata_json={"payment_id": payment.id, "report_id": payment.report_id},
        )
    )
    return payment, True


async def reject_payment(
    session: AsyncSession,
    *,
    payment_id: int,
    admin_telegram_id: int,
    reason: str,
) -> Payment:
    payment = await session.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
    if payment is None:
        raise ValueError("To‘lov topilmadi.")
    if payment.status != "pending":
        raise ValueError("Faqat kutilayotgan to‘lovni rad etish mumkin.")
    payment.status = "rejected"
    payment.reviewed_at = utc_now()
    payment.reviewed_by_telegram_id = admin_telegram_id
    payment.rejection_reason = reason[:300]
    session.add(
        AdminAction(
            actor_telegram_id=admin_telegram_id,
            target_user_id=payment.user_id,
            action="payment_rejected",
            reason=reason[:300],
            metadata_json={"payment_id": payment.id, "report_id": payment.report_id},
        )
    )
    return payment


async def dashboard_stats(session: AsyncSession) -> dict[str, int]:
    now = utc_now()
    local_now = now.astimezone(ZoneInfo("Asia/Almaty"))
    local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    total_users = await session.scalar(select(func.count(User.id))) or 0
    active_today = await session.scalar(
        select(func.count(User.id)).where(User.last_active_at >= local_day_start)
    ) or 0
    active_week = await session.scalar(
        select(func.count(User.id)).where(User.last_active_at >= now - timedelta(days=7))
    ) or 0
    active_month = await session.scalar(
        select(func.count(User.id)).where(User.last_active_at >= now - timedelta(days=30))
    ) or 0
    completed = await session.scalar(
        select(func.count(TestAttempt.id)).where(TestAttempt.status == "completed")
    ) or 0
    grouped = dict(
        (
            await session.execute(
                select(TestAttempt.category_slug, func.count(TestAttempt.id))
                .where(TestAttempt.status == "completed")
                .group_by(TestAttempt.category_slug)
            )
        ).all()
    )
    payment_counts = dict(
        (
            await session.execute(select(Payment.status, func.count(Payment.id)).group_by(Payment.status))
        ).all()
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount_uzs), 0)).where(Payment.status == "approved")
    ) or 0
    return {
        "total_users": total_users,
        "active_today": active_today,
        "active_7_days": active_week,
        "active_30_days": active_month,
        "completed_tests": completed,
        "iq_completed": int(grouped.get("iq", 0)),
        "personality_completed": int(grouped.get("personality", 0)),
        "wellbeing_completed": int(grouped.get("wellbeing", 0)),
        "pending_payments": int(payment_counts.get("pending", 0)),
        "approved_payments": int(payment_counts.get("approved", 0)),
        "rejected_payments": int(payment_counts.get("rejected", 0)),
        "confirmed_revenue_uzs": int(revenue),
    }


async def list_users(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search_term: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    page = max(0, page)
    completed_count = (
        select(func.count(TestAttempt.id))
        .where(TestAttempt.user_id == User.id, TestAttempt.status == "completed")
        .correlate(User)
        .scalar_subquery()
    )
    approved_count = (
        select(func.count(Payment.id))
        .where(Payment.user_id == User.id, Payment.status == "approved")
        .correlate(User)
        .scalar_subquery()
    )
    query = select(User, completed_count.label("completed_tests"), approved_count.label("approved_payments"))
    if search_term:
        term = search_term.strip().lstrip("@")
        pattern = f"%{term}%"
        conditions = [
            User.username.ilike(pattern),
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            (User.first_name + " " + func.coalesce(User.last_name, "")).ilike(pattern),
        ]
        if term.isdecimal():
            conditions.append(User.telegram_id == int(term))
        query = query.where(or_(*conditions))
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await session.execute(
        query.order_by(User.id.desc()).offset(page * page_size).limit(page_size)
    )
    rows = [
        {
            "user": user,
            "completed_tests": completed,
            "approved_payments": approved,
        }
        for user, completed, approved in result.all()
    ]
    return rows, total


async def user_details(session: AsyncSession, user_id: int) -> dict[str, Any] | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    attempts = list(
        (
            await session.execute(
                select(TestAttempt, TestCategory.name_uz)
                .join(TestCategory, TestCategory.slug == TestAttempt.category_slug)
                .where(TestAttempt.user_id == user_id)
                .order_by(TestAttempt.started_at.desc())
                .limit(20)
            )
        ).all()
    )
    payments = list(
        await session.scalars(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.submitted_at.desc()).limit(20)
        )
    )
    return {"user": user, "attempts": attempts, "payments": payments}


async def payment_rows(
    session: AsyncSession,
    *,
    status: str,
    page: int,
    page_size: int = 10,
) -> tuple[list[tuple[Payment, User, str]], int]:
    query = (
        select(Payment, User, TestCategory.name_uz)
        .join(User, User.id == Payment.user_id)
        .join(AssessmentReport, AssessmentReport.id == Payment.report_id)
        .join(TestAttempt, TestAttempt.id == AssessmentReport.attempt_id)
        .join(TestCategory, TestCategory.slug == TestAttempt.category_slug)
        .where(Payment.status == status)
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        (
            await session.execute(
                query.order_by(Payment.submitted_at.desc()).offset(max(0, page) * page_size).limit(page_size)
            )
        ).all()
    )
    return rows, total


async def stats_by_test(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(
                TestAttempt.category_slug,
                TestAttempt.age_band,
                func.count(TestAttempt.id),
                func.avg(TestAttempt.score),
                func.avg(TestAttempt.max_score),
            )
            .where(TestAttempt.status == "completed")
            .group_by(TestAttempt.category_slug, TestAttempt.age_band)
            .order_by(TestAttempt.category_slug, TestAttempt.age_band)
        )
    ).all()
    return [
        {
            "category_slug": category_slug,
            "age_band": age_band,
            "completed": count,
            "average_score": round(float(avg_score or 0), 1),
            "average_max": round(float(avg_max or 0), 1),
        }
        for category_slug, age_band, count, avg_score, avg_max in rows
    ]


async def set_user_status(
    session: AsyncSession,
    *,
    user_id: int,
    admin_telegram_id: int,
    status: str,
    reason: str,
) -> User:
    if status not in {"active", "suspended"}:
        raise ValueError("Invalid account status.")
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise ValueError("Foydalanuvchi topilmadi.")
    user.account_status = status
    session.add(
        AdminAction(
            actor_telegram_id=admin_telegram_id,
            target_user_id=user_id,
            action=f"account_{status}",
            reason=reason[:300],
        )
    )
    return user


async def get_setting(session: AsyncSession, key: str, default: Any = None) -> Any:
    setting = await session.get(BotSetting, key)
    return setting.value_json if setting is not None else default


async def set_category_enabled(
    session: AsyncSession,
    *,
    slug: str,
    enabled: bool,
    admin_telegram_id: int,
) -> None:
    category = await session.get(TestCategory, slug)
    if category is None:
        raise ValueError("Test kategoriyasi topilmadi.")
    category.is_enabled = enabled
    session.add(
        AdminAction(
            actor_telegram_id=admin_telegram_id,
            action="test_category_toggled",
            metadata_json={"category": slug, "enabled": enabled},
        )
    )


async def notification_preferences(
    session: AsyncSession,
    *,
    user_id: int,
    service_opt_in: bool | None = None,
    promotional_opt_in: bool | None = None,
) -> NotificationPreference:
    preference = await session.get(NotificationPreference, user_id)
    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        session.add(preference)
    if service_opt_in is not None:
        preference.service_opt_in = service_opt_in
    if promotional_opt_in is not None:
        preference.promotional_opt_in = promotional_opt_in
    return preference


async def create_broadcast_job(
    session: AsyncSession,
    *,
    audience: str,
    message_text: str,
    photo_file_id: str | None,
    entities_json: list[dict[str, Any]] | None,
    caption_entities_json: list[dict[str, Any]] | None,
    initiated_by_telegram_id: int,
) -> tuple[BroadcastJob, int]:
    if audience not in {"service", "promotional"}:
        raise ValueError("Broadcast audience is invalid.")
    if not message_text.strip():
        raise ValueError("Xabar matni bo‘sh bo‘lishi mumkin emas.")
    if photo_file_id and len(message_text) > 1024:
        raise ValueError("Rasm ostidagi matn 1024 belgidan oshmasligi kerak.")
    if not photo_file_id and len(message_text) > 4000:
        raise ValueError("Xabar 4000 belgidan oshmasligi kerak.")
    job = BroadcastJob(
        status="queued",
        audience=audience,
        message_text=message_text,
        photo_file_id=photo_file_id,
        entities_json=entities_json,
        caption_entities_json=caption_entities_json,
        initiated_by_telegram_id=initiated_by_telegram_id,
    )
    session.add(job)
    await session.flush()
    preference_column = (
        NotificationPreference.service_opt_in
        if audience == "service"
        else NotificationPreference.promotional_opt_in
    )
    eligible = list(
        (
            await session.execute(
                select(User.id)
                .join(NotificationPreference, NotificationPreference.user_id == User.id)
                .where(
                    User.account_status == "active",
                    NotificationPreference.bot_blocked.is_(False),
                    preference_column.is_(True),
                )
            )
        ).scalars()
    )
    session.add_all(
        BroadcastRecipient(job_id=job.id, user_id=user_id, status="pending")
        for user_id in eligible
    )
    if not eligible:
        job.status = "completed"
        job.started_at = utc_now()
        job.completed_at = job.started_at
    session.add(
        AdminAction(
            actor_telegram_id=initiated_by_telegram_id,
            action="broadcast_created",
            metadata_json={"job_id": job.id, "audience": audience, "eligible": len(eligible)},
        )
    )
    return job, len(eligible)


async def broadcast_stats(session: AsyncSession, job_id: int) -> dict[str, int] | None:
    job = await session.get(BroadcastJob, job_id)
    if job is None:
        return None
    counts = dict(
        (
            await session.execute(
                select(BroadcastRecipient.status, func.count(BroadcastRecipient.id))
                .where(BroadcastRecipient.job_id == job_id)
                .group_by(BroadcastRecipient.status)
            )
        ).all()
    )
    total = sum(int(count) for count in counts.values())
    return {
        "job_id": job_id,
        "status": job.status,
        "total": total,
        "sent": int(counts.get("sent", 0)),
        "failed": int(counts.get("failed", 0)),
        "blocked": int(counts.get("blocked", 0)),
        "skipped": int(counts.get("skipped", 0)),
        "remaining": int(counts.get("pending", 0)) + int(counts.get("sending", 0)),
    }


async def latest_broadcast_jobs(session: AsyncSession, limit: int = 10) -> list[BroadcastJob]:
    return list(
        await session.scalars(
            select(BroadcastJob).order_by(BroadcastJob.created_at.desc()).limit(limit)
        )
    )


def display_test_name(slug: str) -> str:
    return TEST_NAMES.get(slug, slug)


def status_counts(items: list[Payment]) -> Counter[str]:
    return Counter(item.status for item in items)

