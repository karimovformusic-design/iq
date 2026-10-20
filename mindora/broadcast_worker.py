from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import MessageEntity
from sqlalchemy import func, select, update

from mindora.constants import BROADCAST_MAX_ATTEMPTS, BROADCAST_SEND_INTERVAL_SECONDS
from mindora.db import SessionFactory
from mindora.models import (
    BroadcastJob,
    BroadcastRecipient,
    NotificationPreference,
    User,
)
from mindora.services import broadcast_stats

logger = logging.getLogger("mindora.broadcast")

UNREACHABLE_MESSAGE_MARKERS = (
    "chat not found",
    "user is deactivated",
    "bot was blocked by the user",
    "bot can't initiate conversation",
    "bot cannot initiate conversation",
    "user not found",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_unreachable_bad_request(error: TelegramBadRequest) -> bool:
    message = (error.message or "").casefold()
    return any(marker in message for marker in UNREACHABLE_MESSAGE_MARKERS)


def _entities(raw: list[dict] | None) -> list[MessageEntity] | None:
    if not raw:
        return None
    return [MessageEntity.model_validate(item) for item in raw]


async def _notify_job_finished(bot: Bot, job_id: int, admin_telegram_id: int) -> None:
    async with SessionFactory() as session:
        stats = await broadcast_stats(session, job_id)
    if stats is None:
        return
    message = (
        f"📊 Broadcast #{job_id} yakunlandi.\n"
        f"Jami: {stats['total']}\n"
        f"Yuborildi: {stats['sent']}\n"
        f"Xato: {stats['failed']}\n"
        f"Botni bloklagan/yetib bo‘lmaydiganlar: {stats['blocked']}\n"
        f"Rozilik sozlamasi o‘zgargani uchun o‘tkazib yuborildi: {stats['skipped']}\n"
        f"Qolgan: {stats['remaining']}"
    )
    try:
        await bot.send_message(admin_telegram_id, message)
    except TelegramAPIError as error:
        logger.warning("Broadcast completion notice failed (%s).", type(error).__name__)


async def recover_interrupted_deliveries(bot: Bot) -> int:
    """Do not replay a delivery interrupted after Telegram may have accepted it."""
    notify: list[tuple[int, int]] = []
    async with SessionFactory() as session, session.begin():
        stuck = list(
            await session.scalars(
                select(BroadcastRecipient).where(BroadcastRecipient.status == "sending")
            )
        )
        for recipient in stuck:
            recipient.status = "failed"
            recipient.result_code = "uncertain_after_restart"
            recipient.claimed_at = None
        job_ids = {recipient.job_id for recipient in stuck}
        for job_id in job_ids:
            admin_id = await _complete_job_if_done(session, job_id)
            if admin_id is not None:
                notify.append((job_id, admin_id))
        count = len(stuck)
    for job_id, admin_id in notify:
        await _notify_job_finished(bot, job_id, admin_id)
    return count


async def _complete_job_if_done(session, job_id: int) -> int | None:
    remaining = await session.scalar(
        select(func.count(BroadcastRecipient.id)).where(
            BroadcastRecipient.job_id == job_id,
            BroadcastRecipient.status.in_(["pending", "sending"]),
        )
    )
    if not remaining:
        job = await session.get(BroadcastJob, job_id, with_for_update=True)
        if job is not None and job.status in {"queued", "running"}:
            job.status = "completed"
            job.completed_at = utc_now()
            return job.initiated_by_telegram_id
    return None


async def _claim_one() -> tuple[BroadcastRecipient, BroadcastJob, User] | None:
    async with SessionFactory() as session, session.begin():
        row = await session.execute(
            select(BroadcastRecipient, BroadcastJob, User)
            .join(BroadcastJob, BroadcastJob.id == BroadcastRecipient.job_id)
            .join(User, User.id == BroadcastRecipient.user_id)
            .where(
                BroadcastRecipient.status == "pending",
                BroadcastRecipient.next_attempt_at <= utc_now(),
                BroadcastJob.status.in_(["queued", "running"]),
            )
            .order_by(BroadcastJob.created_at, BroadcastRecipient.id)
            .with_for_update(skip_locked=True, of=BroadcastRecipient)
            .limit(1)
        )
        claimed = row.one_or_none()
        if claimed is None:
            return None
        recipient, job, user = claimed
        recipient.status = "sending"
        recipient.attempts += 1
        recipient.claimed_at = utc_now()
        job.status = "running"
        if job.started_at is None:
            job.started_at = utc_now()
        await session.flush()
        return recipient, job, user


async def _finish(bot: Bot, recipient_id: int, job_id: int, status: str, result_code: str) -> None:
    notify_admin_id = None
    async with SessionFactory() as session, session.begin():
        recipient = await session.get(BroadcastRecipient, recipient_id, with_for_update=True)
        if recipient is None or recipient.status != "sending":
            return
        recipient.status = status
        recipient.result_code = result_code[:40]
        recipient.claimed_at = None
        if status == "sent":
            recipient.sent_at = utc_now()
        notify_admin_id = await _complete_job_if_done(session, job_id)
    if notify_admin_id is not None:
        await _notify_job_finished(bot, job_id, notify_admin_id)


async def _retry_or_fail(
    recipient_id: int,
    *,
    job_id: int,
    attempts: int,
    delay_seconds: float,
    result_code: str,
    bot: Bot,
) -> None:
    notify_admin_id = None
    async with SessionFactory() as session, session.begin():
        recipient = await session.get(BroadcastRecipient, recipient_id, with_for_update=True)
        if recipient is None or recipient.status != "sending":
            return
        if attempts >= BROADCAST_MAX_ATTEMPTS:
            recipient.status = "failed"
            recipient.result_code = result_code[:40]
            recipient.claimed_at = None
            notify_admin_id = await _complete_job_if_done(session, job_id)
        else:
            recipient.status = "pending"
            recipient.result_code = result_code[:40]
            recipient.next_attempt_at = utc_now() + timedelta(seconds=max(1, min(delay_seconds, 300)))
            recipient.claimed_at = None
    if notify_admin_id is not None:
        await _notify_job_finished(bot, job_id, notify_admin_id)


async def _mark_blocked(bot: Bot, recipient_id: int, job_id: int, user_id: int) -> None:
    notify_admin_id = None
    async with SessionFactory() as session, session.begin():
        recipient = await session.get(BroadcastRecipient, recipient_id, with_for_update=True)
        if recipient is not None and recipient.status == "sending":
            recipient.status = "blocked"
            recipient.result_code = "blocked_by_user"
            recipient.claimed_at = None
        preference = await session.get(NotificationPreference, user_id, with_for_update=True)
        if preference is not None:
            preference.bot_blocked = True
        notify_admin_id = await _complete_job_if_done(session, job_id)
    if notify_admin_id is not None:
        await _notify_job_finished(bot, job_id, notify_admin_id)


async def _send_one(bot: Bot) -> bool:
    claimed = await _claim_one()
    if claimed is None:
        return False
    recipient, job, user = claimed
    async with SessionFactory() as session:
        preference = await session.get(NotificationPreference, user.id)
    still_eligible = (
        user.account_status == "active"
        and preference is not None
        and not preference.bot_blocked
        and (
            preference.service_opt_in
            if job.audience == "service"
            else preference.promotional_opt_in
        )
    )
    if not still_eligible:
        await _finish(bot, recipient.id, job.id, "skipped", "no_longer_eligible")
        return True
    try:
        if job.photo_file_id:
            await bot.send_photo(
                chat_id=user.telegram_id,
                photo=job.photo_file_id,
                caption=job.message_text,
                caption_entities=_entities(job.caption_entities_json),
            )
        else:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=job.message_text,
                entities=_entities(job.entities_json),
                disable_web_page_preview=True,
            )
        await _finish(bot, recipient.id, job.id, "sent", "sent")
    except TelegramForbiddenError:
        await _mark_blocked(bot, recipient.id, job.id, user.id)
    except TelegramRetryAfter as error:
        await _retry_or_fail(
            recipient.id,
            job_id=job.id,
            attempts=recipient.attempts,
            delay_seconds=float(error.retry_after),
            result_code="rate_limited",
            bot=bot,
        )
    except TelegramServerError:
        await _retry_or_fail(
            recipient.id,
            job_id=job.id,
            attempts=recipient.attempts,
            delay_seconds=2**recipient.attempts,
            result_code="telegram_temporary_error",
            bot=bot,
        )
    except TelegramNetworkError:
        # Delivery may have reached Telegram before the connection timed out.
        # Treat it as terminal rather than risk a duplicate after restart.
        await _finish(bot, recipient.id, job.id, "failed", "delivery_uncertain")
    except TelegramBadRequest as error:
        if _is_unreachable_bad_request(error):
            await _mark_blocked(bot, recipient.id, job.id, user.id)
        else:
            await _finish(bot, recipient.id, job.id, "failed", "telegram_rejected")
            logger.warning("Broadcast delivery rejected by Telegram (%s).", type(error).__name__)
    except TelegramAPIError as error:
        code = "invalid_media" if job.photo_file_id else "telegram_rejected"
        await _finish(bot, recipient.id, job.id, "failed", code)
        logger.warning("Broadcast delivery rejected by Telegram (%s).", type(error).__name__)
    except Exception as error:
        await _finish(bot, recipient.id, job.id, "failed", "internal_delivery_error")
        logger.error("Broadcast delivery failed (%s).", type(error).__name__)
    return True


async def run_broadcast_worker(bot: Bot) -> None:
    recovered = await recover_interrupted_deliveries(bot)
    if recovered:
        logger.warning("Marked %d interrupted broadcast deliveries as uncertain failures.", recovered)
    while True:
        try:
            sent_or_claimed = await _send_one(bot)
            if sent_or_claimed:
                await asyncio.sleep(BROADCAST_SEND_INTERVAL_SECONDS)
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Broadcast worker cycle failed (%s).", type(error).__name__)
            await asyncio.sleep(2)
