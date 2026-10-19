from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from mindora.constants import (
    ADMIN_CONTACT,
    PAYMENT_CARD_NUMBER,
    PAYMENT_RECIPIENT,
    PRICE_PER_REPORT_UZS,
    USER_PAGE_SIZE,
    TEST_NAMES,
)
from mindora.db import SessionFactory
from mindora.keyboards import (
    admin_menu,
    broadcast_confirmation_keyboard,
    broadcast_start_keyboard,
    category_toggle_keyboard,
    notification_settings,
    page_controls,
    payment_rejection_confirmation,
    payment_review_keyboard,
    question_options,
    report_keyboard,
    test_categories,
    user_detail_keyboard,
    user_main_menu,
)
from mindora.models import (
    AdminAction,
    AssessmentReport,
    BotSetting,
    BroadcastJob,
    ConversationState,
    NotificationPreference,
    Payment,
    Question,
    TestAttempt,
    TestCategory,
    User,
)
from mindora.services import (
    approve_payment,
    broadcast_stats,
    create_broadcast_job,
    dashboard_stats,
    get_report_for_user,
    get_setting,
    get_user_by_telegram_id,
    list_users,
    payment_rows,
    question_for_attempt_position,
    record_answer,
    reject_payment,
    set_category_enabled,
    set_user_status,
    start_attempt,
    stats_by_test,
    submit_receipt,
    upsert_user,
    user_details,
)
from mindora.settings import is_authorized_admin, settings

logger = logging.getLogger("mindora.bot")
router = Router(name="mindora")
LOCAL_TZ = ZoneInfo("Asia/Almaty")
_LAST_SENSITIVE_ADMIN_ACTION: dict[int, float] = {}


def format_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


def format_uzs(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " UZS"


def safe_int(value: str) -> int | None:
    if not value.isdecimal():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"


async def _require_private_callback(callback: CallbackQuery) -> bool:
    if callback.message is not None and callback.message.chat.type == "private":
        return True
    await callback.answer("Botdan shaxsiy chatda foydalaning.", show_alert=True)
    return False


def entity_data(entities) -> list[dict] | None:
    if not entities:
        return None
    return [entity.model_dump(mode="json", exclude_none=True) for entity in entities]


async def set_state(
    session,
    telegram_id: int,
    state: str,
    payload: dict | None = None,
) -> None:
    current = await session.get(ConversationState, telegram_id)
    if current is None:
        session.add(
            ConversationState(
                telegram_id=telegram_id,
                state=state,
                payload=payload or {},
            )
        )
    else:
        current.state = state
        current.payload = payload or {}


async def clear_state(session, telegram_id: int) -> None:
    current = await session.get(ConversationState, telegram_id)
    if current is not None:
        await session.delete(current)


async def load_state(telegram_id: int) -> tuple[str | None, dict]:
    async with SessionFactory() as session:
        state = await session.get(ConversationState, telegram_id)
        if state is None:
            return None, {}
        return state.state, dict(state.payload or {})


async def require_admin_callback(callback: CallbackQuery) -> bool:
    if is_authorized_admin(callback.from_user.id, settings.admin_ids):
        return True
    await callback.answer("Bu bo‘lim faqat vakolatli administratorlar uchun.", show_alert=True)
    return False


async def rate_limit_sensitive_admin_action(callback: CallbackQuery, data: str) -> bool:
    sensitive = (
        "admin:user:suspend-confirm:",
        "admin:user:reactivate:",
        "admin:payment:approve:",
        "admin:payment:reject-confirm:",
        "admin:test-toggle:",
        "admin:broadcast:confirm",
    )
    if not data.startswith(sensitive):
        return True
    now = time.monotonic()
    last = _LAST_SENSITIVE_ADMIN_ACTION.get(callback.from_user.id, 0.0)
    if now - last < 0.75:
        await callback.answer("Bu amal juda tez takrorlandi. Biroz kuting.", show_alert=True)
        return False
    _LAST_SENSITIVE_ADMIN_ACTION[callback.from_user.id] = now
    return True


async def edit_or_answer(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


async def get_active_user(telegram_id: int) -> User | None:
    async with SessionFactory() as session, session.begin():
        user = await get_user_by_telegram_id(session, telegram_id)
        if user is not None:
            user.last_active_at = datetime.now(timezone.utc)
        return user


async def render_question(bot: Bot, chat_id: int, attempt_id: int, position: int, telegram_id: int) -> None:
    async with SessionFactory() as session:
        pair = await question_for_attempt_position(
            session,
            attempt_id=attempt_id,
            telegram_id=telegram_id,
            position=position,
        )
        if pair is None:
            return
        attempt, question = pair
        category_name = TEST_NAMES.get(attempt.category_slug, attempt.category_slug)
        prompt = (
            f"{category_name}\n"
            f"Savol {position + 1}/{len(attempt.question_order)}\n\n"
            f"{question.prompt_uz}"
        )
        keyboard = question_options(attempt.id, position, question.options_uz)
    await bot.send_message(chat_id, prompt, reply_markup=keyboard)


async def render_users(
    target: Message | CallbackQuery,
    *,
    page: int,
    search_term: str | None = None,
) -> None:
    async with SessionFactory() as session:
        rows, total = await list_users(
            session,
            page=page,
            page_size=USER_PAGE_SIZE,
            search_term=search_term,
        )
        lines = [f"👥 Foydalanuvchilar · jami: {total}"]
        keyboard_rows = []
        for row in rows:
            user = row["user"]
            username = f"@{user.username}" if user.username else "username yo‘q"
            full_name = " ".join(part for part in [user.first_name, user.last_name] if part) or "—"
            lines.append(
                f"\n#{user.id} · Telegram ID: {user.telegram_id}\n"
                f"{full_name} · {username} · yosh: {user.age or '—'} · {user.account_status}\n"
                f"Ro‘yxat: {format_date(user.registered_at)} · Faollik: {format_date(user.last_active_at)}\n"
                f"Testlar: {row['completed_tests']} · Tasdiqlangan to‘lovlar: {row['approved_payments']}"
            )
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Ko‘rish · #{user.id} {full_name[:30]}",
                        callback_data=f"admin:user:open:{user.id}",
                    )
                ]
            )
    controls = page_controls(
        namespace="admin:users:page",
        page=page,
        total=total,
        page_size=USER_PAGE_SIZE,
        back_callback="admin:menu",
        search=True,
    )
    keyboard_rows.extend(controls.inline_keyboard)
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    text = "\n".join(lines)
    if search_term:
        text = f"🔍 Qidiruv: {search_term}\n\n{text}"
    if isinstance(target, CallbackQuery):
        await edit_or_answer(target, text[:3900], markup)
    else:
        await target.answer(text[:3900], reply_markup=markup)


async def show_user_detail(callback: CallbackQuery, user_id: int) -> None:
    async with SessionFactory() as session:
        details = await user_details(session, user_id)
        if details is None:
            await edit_or_answer(callback, "Foydalanuvchi topilmadi.", admin_menu())
            return
        user = details["user"]
        name = " ".join(part for part in [user.first_name, user.last_name] if part) or "—"
        lines = [
            f"👤 Foydalanuvchi #{user.id}",
            f"Telegram ID: {user.telegram_id}",
            f"Username: @{user.username}" if user.username else "Username: mavjud emas",
            f"Ism: {name}",
            f"Yosh: {user.age or '—'}",
            f"Ro‘yxatdan o‘tgan: {format_date(user.registered_at)}",
            f"So‘nggi faollik: {format_date(user.last_active_at)}",
            f"Hisob holati: {user.account_status}",
            "",
            "Oxirgi testlar:",
        ]
        if details["attempts"]:
            for attempt, category_name in details["attempts"][:10]:
                score = f" · natija {attempt.score}/{attempt.max_score}" if attempt.score is not None else ""
                lines.append(
                    f"• {category_name} · {attempt.status}{score} · {format_date(attempt.started_at)}"
                )
        else:
            lines.append("• Test tarixi yo‘q")
        lines.append("\nTo‘lovlar:")
        if details["payments"]:
            for payment in details["payments"][:10]:
                lines.append(
                    f"• #{payment.id} · {payment.status} · {format_uzs(payment.amount_uzs)} · "
                    f"{format_date(payment.submitted_at)}"
                )
        else:
            lines.append("• To‘lov tarixi yo‘q")
        text = "\n".join(lines)
        markup = user_detail_keyboard(user.id, user.account_status)
    await edit_or_answer(callback, text[:3900], markup)


async def show_payment_detail(callback: CallbackQuery, payment_id: int, bot: Bot) -> None:
    async with SessionFactory() as session:
        payment = await session.get(Payment, payment_id)
        if payment is None:
            await edit_or_answer(callback, "To‘lov topilmadi.", admin_menu())
            return
        user = await session.get(User, payment.user_id)
        report = await session.get(AssessmentReport, payment.report_id)
        attempt = await session.get(TestAttempt, report.attempt_id) if report else None
        category = await session.get(TestCategory, attempt.category_slug) if attempt else None
        if user is None:
            await edit_or_answer(callback, "Foydalanuvchi ma’lumoti topilmadi.", admin_menu())
            return
        lines = [
            f"💳 To‘lov #{payment.id}",
            f"Foydalanuvchi: #{user.id} · Telegram ID {user.telegram_id}",
            f"Ism: {' '.join(part for part in [user.first_name, user.last_name] if part) or '—'}",
            f"Test: {category.name_uz if category else '—'}",
            f"Summa: {format_uzs(payment.amount_uzs)}",
            f"Holat: {payment.status}",
            f"Chek yuborilgan: {format_date(payment.submitted_at)}",
        ]
        markup = payment_review_keyboard(payment.id) if payment.status == "pending" else admin_menu()
        receipt_id = payment.receipt_file_id
        receipt_kind = payment.receipt_kind
    if callback.message is None:
        return
    await callback.message.answer("\n".join(lines), reply_markup=markup)
    try:
        if receipt_kind == "photo":
            await bot.send_photo(callback.message.chat.id, receipt_id, caption="Yuborilgan chek")
        else:
            await bot.send_document(callback.message.chat.id, receipt_id, caption="Yuborilgan chek")
    except TelegramAPIError as error:
        logger.warning("Receipt preview failed (%s).", type(error).__name__)
        await callback.message.answer("Chekni yuklab bo‘lmadi; to‘lov kartasidagi chekni tekshiring.")


async def show_payment_page(
    callback: CallbackQuery,
    *,
    status: str,
    page: int,
) -> None:
    async with SessionFactory() as session:
        rows, total = await payment_rows(session, status=status, page=page, page_size=10)
        lines = [f"💳 {status.title()} to‘lovlar · jami: {total}"]
        buttons = []
        for payment, user, category_name in rows:
            lines.append(
                f"\n#{payment.id} · {format_uzs(payment.amount_uzs)} · "
                f"Foydalanuvchi #{user.id} ({user.telegram_id}) · {category_name} · "
                f"{format_date(payment.submitted_at)}"
            )
            buttons.append(
                [InlineKeyboardButton(text=f"To‘lov #{payment.id}", callback_data=f"admin:payment:detail:{payment.id}")]
            )
    controls = page_controls(
        namespace=f"admin:payments:{status}",
        page=page,
        total=total,
        page_size=10,
        back_callback="admin:menu",
    )
    buttons.extend(controls.inline_keyboard)
    await edit_or_answer(callback, "\n".join(lines)[:3900], InlineKeyboardMarkup(inline_keyboard=buttons))


async def show_user_payments(callback: CallbackQuery, user_id: int) -> None:
    async with SessionFactory() as session:
        user = await session.get(User, user_id)
        payments = list(
            await session.scalars(
                select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(Payment.submitted_at.desc())
                .limit(20)
            )
        )
    if user is None:
        await edit_or_answer(callback, "Foydalanuvchi topilmadi.", admin_menu())
        return
    text = f"💳 Foydalanuvchi #{user.id} to‘lovlari\n"
    text += "\n".join(
        f"#{item.id} · {item.status} · {format_uzs(item.amount_uzs)} · {format_date(item.submitted_at)}"
        for item in payments
    ) or "To‘lovlar topilmadi."
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"To‘lov #{item.id}",
                    callback_data=f"admin:payment:detail:{item.id}",
                )
            ]
            for item in payments
        ]
        + [[InlineKeyboardButton(text="🔙 Foydalanuvchi", callback_data=f"admin:user:open:{user_id}")]]
    )
    await edit_or_answer(callback, text[:3900], markup)


async def show_user_tests(callback: CallbackQuery, user_id: int) -> None:
    async with SessionFactory() as session:
        user = await session.get(User, user_id)
        rows = list(
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
    if user is None:
        await edit_or_answer(callback, "Foydalanuvchi topilmadi.", admin_menu())
        return
    lines = [f"🧠 Foydalanuvchi #{user.id} testlari"]
    lines.extend(
        f"• {category} · {attempt.status}"
        f"{f' · {attempt.score}/{attempt.max_score}' if attempt.score is not None else ''}"
        f" · {format_date(attempt.started_at)}"
        for attempt, category in rows
    )
    if not rows:
        lines.append("Testlar topilmadi.")
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Foydalanuvchi", callback_data=f"admin:user:open:{user_id}")]]
    )
    await edit_or_answer(callback, "\n".join(lines)[:3900], markup)


async def show_broadcast_results(callback: CallbackQuery, job_id: int) -> None:
    async with SessionFactory() as session:
        stats = await broadcast_stats(session, job_id)
        job = await session.get(BroadcastJob, job_id)
    if stats is None or job is None:
        await edit_or_answer(callback, "Xabar yuborish ishi topilmadi.", broadcast_start_keyboard())
        return
    text = (
        f"📊 Broadcast #{job.id}\n"
        f"Holat: {stats['status']}\n"
        f"Jami qabul qiluvchilar: {stats['total']}\n"
        f"Yuborildi: {stats['sent']}\n"
        f"Yuborilmadi: {stats['failed']}\n"
        f"Botni bloklagan yoki yetib bo‘lmaydiganlar: {stats['blocked']}\n"
        f"Rozilik sozlamasi o‘zgargani uchun o‘tkazib yuborildi: {stats['skipped']}\n"
        f"Qolgan: {stats['remaining']}"
    )
    await edit_or_answer(
        callback,
        text,
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"admin:broadcast:results:{job.id}")],
                [InlineKeyboardButton(text="🔙 Broadcast", callback_data="admin:broadcast")],
                [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")],
            ]
        ),
    )


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_private_chat(message):
        await message.answer("Maxfiy ma’lumotlar uchun botni shaxsiy chatda oching.")
        return
    telegram_user = message.from_user
    async with SessionFactory() as session, session.begin():
        user = await upsert_user(
            session,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )
        await clear_state(session, telegram_user.id)
        if user.age is None:
            await set_state(session, telegram_user.id, "awaiting_age", {})
            ask_age = True
            suspended = False
        else:
            ask_age = False
            suspended = user.account_status == "suspended"
    if suspended:
        await message.answer(
            f"Hisobingiz vaqtincha to‘xtatilgan. Yordam uchun {ADMIN_CONTACT} bilan bog‘laning."
        )
    elif ask_age:
        await message.answer(
            "Assalomu alaykum! MINDORA’ga xush kelibsiz.\n"
            "Sizga mos savollarni tanlash uchun yoshingizni kiriting (7–70)."
        )
    else:
        await message.answer(
            "MINDORA bosh menyusi. Test natijalari o‘zini anglash uchun mo‘ljallangan; "
            "ular klinik tashxis hisoblanmaydi.",
            reply_markup=user_main_menu(is_authorized_admin(telegram_user.id, settings.admin_ids)),
        )


@router.message(Command("menu"))
async def menu_command(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_private_chat(message):
        await message.answer("Bot menyusidan shaxsiy chatda foydalaning.")
        return
    user = await get_active_user(message.from_user.id)
    if user is None:
        await message.answer("Boshlash uchun /start buyrug‘ini yuboring.")
    elif user.account_status == "suspended":
        await message.answer(f"Hisobingiz vaqtincha to‘xtatilgan. {ADMIN_CONTACT} bilan bog‘laning.")
    elif user.age is None:
        await message.answer("Davom etish uchun yoshingizni kiriting (7–70).")
    else:
        await message.answer(
            "MINDORA bosh menyusi.",
            reply_markup=user_main_menu(is_authorized_admin(message.from_user.id, settings.admin_ids)),
        )


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if not _is_private_chat(message):
        await message.answer("Administrator panelini shaxsiy chatda oching.")
        return
    if message.from_user is None or not is_authorized_admin(message.from_user.id, settings.admin_ids):
        await message.answer("Bu buyruq faqat vakolatli administratorlar uchun.")
        return
    await message.answer("🛡 MINDORA administrator paneli", reply_markup=admin_menu())


@router.message(Command("id"))
async def telegram_id_command(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_private_chat(message):
        await message.answer("Telegram ID raqamingizni shaxsiy chatda oling.")
        return
    await message.answer(
        f"Sizning Telegram ID raqamingiz: {message.from_user.id}\n"
        "Ushbu raqamni ADMIN_IDS sozlamasiga faqat administrator bo‘lishi kerak bo‘lgan "
        "Telegram hisoblari uchun kiriting."
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message) -> None:
    if message.from_user is None:
        return
    if not _is_private_chat(message):
        await message.answer("Joriy amalni shaxsiy chatda bekor qiling.")
        return
    async with SessionFactory() as session, session.begin():
        await clear_state(session, message.from_user.id)
    await message.answer("Joriy amal bekor qilindi.", reply_markup=user_main_menu(
        is_authorized_admin(message.from_user.id, settings.admin_ids)
    ))


@router.callback_query(F.data.startswith("test:answer:"))
async def answer_question(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None:
        return
    if not await _require_private_callback(callback):
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 5 or not all(part.isdecimal() for part in parts[2:]):
        await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
        return
    attempt_id, position, answer_index = map(int, parts[2:])
    user = await get_active_user(callback.from_user.id)
    if user is None or user.account_status != "active":
        await callback.answer("Hisob faol emas. /start buyrug‘ini yuboring.", show_alert=True)
        return
    try:
        async with SessionFactory() as session, session.begin():
            finished, report = await record_answer(
                session,
                attempt_id=attempt_id,
                telegram_id=callback.from_user.id,
                position=position,
                answer_index=answer_index,
            )
            if finished and report is not None:
                report_id = report.id
                attempt = await session.get(TestAttempt, report.attempt_id)
                category_name = TEST_NAMES.get(attempt.category_slug, attempt.category_slug)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.answer("Javob qabul qilindi.")
    if finished:
        if callback.message:
            await callback.message.answer(
                f"Test yakunlandi: {category_name}.\n"
                f"Shaxsiy batafsil hisobot tayyor. Hisobotni ochish uchun "
                f"{format_uzs(PRICE_PER_REPORT_UZS)} to‘lov qilib chek yuboring.",
                reply_markup=report_keyboard(report_id, released=False),
            )
    else:
        await render_question(bot, callback.from_user.id, attempt_id, position + 1, callback.from_user.id)


@router.callback_query(F.data.startswith("user:"))
async def user_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    if not await _require_private_callback(callback):
        return
    data = callback.data or ""
    user = await get_active_user(callback.from_user.id)
    if data == "user:menu":
        await callback.answer()
        if user is None or user.age is None:
            await edit_or_answer(callback, "Davom etish uchun /start buyrug‘ini yuboring.")
        elif user.account_status == "suspended":
            await edit_or_answer(callback, f"Hisobingiz vaqtincha to‘xtatilgan. {ADMIN_CONTACT} bilan bog‘laning.")
        else:
            await edit_or_answer(
                callback,
                "MINDORA bosh menyusi.",
                user_main_menu(is_authorized_admin(callback.from_user.id, settings.admin_ids)),
            )
        return
    if data == "user:pay-cancel":
        async with SessionFactory() as session, session.begin():
            await clear_state(session, callback.from_user.id)
        await callback.answer("To‘lov bekor qilindi.")
        await edit_or_answer(
            callback,
            "To‘lov jarayoni bekor qilindi.",
            user_main_menu(is_authorized_admin(callback.from_user.id, settings.admin_ids)),
        )
        return
    if user is None or user.account_status != "active":
        await callback.answer("Hisob faol emas. /start buyrug‘ini yuboring.", show_alert=True)
        return
    if user.age is None:
        await callback.answer("Avval yoshingizni kiriting.", show_alert=True)
        return

    if data == "user:test-list":
        async with SessionFactory() as session:
            categories = list(
                await session.scalars(
                    select(TestCategory).where(TestCategory.is_enabled.is_(True)).order_by(TestCategory.sort_order)
                )
            )
        await callback.answer()
        await edit_or_answer(
            callback,
            "Test turini tanlang. Har bir testda savollar yoshingizga mos tanlanadi.",
            test_categories(categories),
        )
        return

    if data.startswith("user:test-start:"):
        slug = data.removeprefix("user:test-start:")
        if slug not in TEST_NAMES:
            await callback.answer("Test turi noto‘g‘ri.", show_alert=True)
            return
        try:
            async with SessionFactory() as session, session.begin():
                attempt = await start_attempt(
                    session,
                    telegram_id=callback.from_user.id,
                    category_slug=slug,
                )
                attempt_id = attempt.id
        except (ValueError, PermissionError, RuntimeError) as error:
            await callback.answer(str(error), show_alert=True)
            return
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "10 ta savol beriladi. Har bir savolga bir marta javob bering. "
                "Javoblar administratorlarga ko‘rsatilmaydi."
            )
        await render_question(callback.bot, callback.from_user.id, attempt_id, 0, callback.from_user.id)
        return

    if data == "user:reports":
        async with SessionFactory() as session:
            rows = list(
                (
                    await session.execute(
                        select(AssessmentReport, TestCategory.name_uz, TestAttempt.score, TestAttempt.max_score)
                        .join(TestAttempt, TestAttempt.id == AssessmentReport.attempt_id)
                        .join(TestCategory, TestCategory.slug == TestAttempt.category_slug)
                        .where(AssessmentReport.user_id == user.id)
                        .order_by(AssessmentReport.generated_at.desc())
                        .limit(20)
                    )
                ).all()
            )
        lines = ["📄 Hisobotlaringiz"]
        buttons = []
        for report, category_name, score, maximum in rows:
            status = "ochiq" if report.released_to_user else "to‘lov kutilmoqda"
            lines.append(f"\n#{report.id} · {category_name} · natija {score}/{maximum} · {status}")
            buttons.append([InlineKeyboardButton(
                text=f"Hisobot #{report.id}",
                callback_data=f"user:report:{report.id}",
            )])
        if not rows:
            lines.append("Hozircha yakunlangan test yo‘q.")
        buttons.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="user:menu")])
        await callback.answer()
        await edit_or_answer(callback, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    if data.startswith("user:report:"):
        report_id = safe_int(data.removeprefix("user:report:"))
        if report_id is None:
            await callback.answer("Hisobot raqami noto‘g‘ri.", show_alert=True)
            return
        async with SessionFactory() as session:
            owned = await get_report_for_user(session, report_id=report_id, telegram_id=callback.from_user.id)
            report = owned[0] if owned else None
        if report is None:
            await callback.answer("Hisobot topilmadi.", show_alert=True)
        elif not report.released_to_user:
            await callback.answer("Hisobotni ochish uchun avval to‘lovni tasdiqlatish kerak.", show_alert=True)
        else:
            await callback.answer()
            if callback.message:
                await callback.message.answer(report.report_text)
        return

    if data.startswith("user:pay:"):
        report_id = safe_int(data.removeprefix("user:pay:"))
        if report_id is None:
            await callback.answer("Hisobot raqami noto‘g‘ri.", show_alert=True)
            return
        async with SessionFactory() as session:
            owned = await get_report_for_user(session, report_id=report_id, telegram_id=callback.from_user.id)
            report = owned[0] if owned else None
            pending = None
            if report is not None:
                pending = await session.scalar(
                    select(Payment).where(Payment.report_id == report_id, Payment.status == "pending")
                )
        if report is None:
            await callback.answer("Hisobot topilmadi.", show_alert=True)
        elif report.released_to_user:
            await callback.answer("Hisobot uchun to‘lov tasdiqlangan.", show_alert=True)
        else:
            async with SessionFactory() as session, session.begin():
                await set_state(
                    session,
                    callback.from_user.id,
                    "awaiting_receipt",
                    {"report_id": report_id},
                )
            await callback.answer()
            await edit_or_answer(
                callback,
                (
                    f"Hisobot uchun {format_uzs(PRICE_PER_REPORT_UZS)} to‘lang.\n\n"
                    f"Qabul qiluvchi: {PAYMENT_RECIPIENT}\n"
                    f"Karta raqami: {PAYMENT_CARD_NUMBER}\n"
                    f"Izoh: MINDORA hisobot #{report_id}\n\n"
                    f"To‘lovdan keyin chek rasmini yoki PDF faylini shu yerga yuboring. "
                    f"Administrator tekshiradi. Savol bo‘lsa: {ADMIN_CONTACT}."
                    + ("\n\nOldingi chek hali tekshirilmoqda; yangi chek yuborsangiz, u almashtiriladi." if pending else "")
                ),
                InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="user:pay-cancel")]
                    ]
                ),
            )
        return

    if data == "user:notifications":
        async with SessionFactory() as session:
            preference = await session.get(NotificationPreference, user.id)
            service = preference.service_opt_in if preference else True
            promotional = preference.promotional_opt_in if preference else False
        await callback.answer()
        await edit_or_answer(
            callback,
            "Bildirishnoma sozlamalari. Reklama xabarlari faqat rozilik berganingizda yuboriladi.",
            notification_settings(service, promotional),
        )
        return

    if data in {"user:notifications:service", "user:notifications:promotional"}:
        async with SessionFactory() as session, session.begin():
            preference = await session.get(NotificationPreference, user.id)
            if preference is None:
                preference = NotificationPreference(user_id=user.id)
                session.add(preference)
                await session.flush()
            if data.endswith("service"):
                preference.service_opt_in = not preference.service_opt_in
            else:
                preference.promotional_opt_in = not preference.promotional_opt_in
            service = preference.service_opt_in
            promotional = preference.promotional_opt_in
        await callback.answer("Sozlama saqlandi.")
        await edit_or_answer(
            callback,
            "Bildirishnoma sozlamalari.",
            notification_settings(service, promotional),
        )
        return

    await callback.answer("Noma’lum amal.", show_alert=True)


@router.callback_query(F.data.startswith("admin:"))
async def admin_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or not await _require_private_callback(callback):
        return
    if not await require_admin_callback(callback):
        return
    data = callback.data or ""
    if not await rate_limit_sensitive_admin_action(callback, data):
        return
    await get_active_user(callback.from_user.id)
    await callback.answer()

    if data == "admin:menu":
        await edit_or_answer(callback, "🛡 MINDORA administrator paneli", admin_menu())
        return

    if data == "admin:dashboard":
        async with SessionFactory() as session:
            stats = await dashboard_stats(session)
        text = (
            "📊 MINDORA dashboard\n\n"
            f"Jami foydalanuvchilar: {stats['total_users']}\n"
            f"Bugun faol: {stats['active_today']}\n"
            f"So‘nggi 7 kunda faol: {stats['active_7_days']}\n"
            f"So‘nggi 30 kunda faol: {stats['active_30_days']}\n\n"
            f"Yakunlangan testlar: {stats['completed_tests']}\n"
            f"• IQ uslubidagi: {stats['iq_completed']}\n"
            f"• Shaxsiyat: {stats['personality_completed']}\n"
            f"• Psixologik farovonlik: {stats['wellbeing_completed']}\n\n"
            f"Kutilayotgan to‘lovlar: {stats['pending_payments']}\n"
            f"Tasdiqlangan to‘lovlar: {stats['approved_payments']}\n"
            f"Rad etilgan to‘lovlar: {stats['rejected_payments']}\n"
            f"Tasdiqlangan tushum: {format_uzs(stats['confirmed_revenue_uzs'])}"
        )
        await edit_or_answer(callback, text, admin_menu())
        return

    if data.startswith("admin:users:page:"):
        page = safe_int(data.removeprefix("admin:users:page:"))
        if page is None and data.endswith(":0"):
            page = 0
        if page is None:
            await edit_or_answer(callback, "Sahifa raqami noto‘g‘ri.", admin_menu())
            return
        state, payload = await load_state(callback.from_user.id)
        if state == "admin_user_search_results":
            await render_users(callback, page=page, search_term=payload.get("search_term"))
            return
        await render_users(callback, page=page)
        return

    if data.startswith("admin:users:searchpage:"):
        page_text = data.removeprefix("admin:users:searchpage:")
        if not page_text.isdecimal():
            await edit_or_answer(callback, "Sahifa raqami noto‘g‘ri.", admin_menu())
            return
        state, payload = await load_state(callback.from_user.id)
        if state != "admin_user_search_results":
            await edit_or_answer(callback, "Qidiruv muddati tugagan. Qayta qidiring.", admin_menu())
            return
        await render_users(callback, page=int(page_text), search_term=payload.get("search_term"))
        return

    if data == "admin:users:search":
        async with SessionFactory() as session, session.begin():
            await set_state(session, callback.from_user.id, "admin_user_search", {})
        await edit_or_answer(callback, "Telegram ID, username yoki ro‘yxatdan o‘tgan ismni yuboring.")
        return

    if data.startswith("admin:user:open:"):
        user_id = safe_int(data.removeprefix("admin:user:open:"))
        if user_id is None:
            await edit_or_answer(callback, "Foydalanuvchi raqami noto‘g‘ri.", admin_menu())
        else:
            await show_user_detail(callback, user_id)
        return

    if data.startswith("admin:user:payments:"):
        user_id = safe_int(data.removeprefix("admin:user:payments:"))
        if user_id is None:
            await edit_or_answer(callback, "Foydalanuvchi raqami noto‘g‘ri.", admin_menu())
        else:
            await show_user_payments(callback, user_id)
        return

    if data.startswith("admin:user:tests:"):
        user_id = safe_int(data.removeprefix("admin:user:tests:"))
        if user_id is None:
            await edit_or_answer(callback, "Foydalanuvchi raqami noto‘g‘ri.", admin_menu())
        else:
            await show_user_tests(callback, user_id)
        return

    if data.startswith("admin:user:suspend:"):
        user_id = safe_int(data.removeprefix("admin:user:suspend:"))
        if user_id is None:
            await edit_or_answer(callback, "Foydalanuvchi raqami noto‘g‘ri.", admin_menu())
            return
        async with SessionFactory() as session:
            user = await session.get(User, user_id)
        if user is None or user.account_status != "active":
            await edit_or_answer(callback, "Foydalanuvchi faol hisobda emas.", admin_menu())
            return
        async with SessionFactory() as session, session.begin():
            await set_state(session, callback.from_user.id, "admin_suspend_reason", {"user_id": user_id})
        await edit_or_answer(
            callback,
            f"Foydalanuvchi #{user_id} hisobini to‘xtatish sababini kiriting. Bekor qilish uchun /cancel yuboring.",
        )
        return

    if data.startswith("admin:user:suspend-confirm:"):
        user_id = safe_int(data.removeprefix("admin:user:suspend-confirm:"))
        state, payload = await load_state(callback.from_user.id)
        reason = payload.get("reason")
        if user_id is None or state != "admin_suspend_confirm" or payload.get("user_id") != user_id or not reason:
            await edit_or_answer(callback, "Tasdiqlash muddati tugagan. Qayta boshlang.", admin_menu())
            return
        async with SessionFactory() as session, session.begin():
            user = await set_user_status(
                session,
                user_id=user_id,
                admin_telegram_id=callback.from_user.id,
                status="suspended",
                reason=reason,
            )
            telegram_id = user.telegram_id
            await clear_state(session, callback.from_user.id)
        try:
            await bot.send_message(
                telegram_id,
                f"Hisobingiz administrator tomonidan vaqtincha to‘xtatildi. "
                f"Savol bo‘lsa, {ADMIN_CONTACT} bilan bog‘laning.",
            )
        except TelegramAPIError:
            pass
        await edit_or_answer(callback, f"Foydalanuvchi #{user_id} to‘xtatildi. Amal jurnali saqlandi.", admin_menu())
        return

    if data.startswith("admin:user:reactivate:"):
        user_id = safe_int(data.removeprefix("admin:user:reactivate:"))
        if user_id is None:
            await edit_or_answer(callback, "Foydalanuvchi raqami noto‘g‘ri.", admin_menu())
            return
        async with SessionFactory() as session, session.begin():
            user = await set_user_status(
                session,
                user_id=user_id,
                admin_telegram_id=callback.from_user.id,
                status="active",
                reason="Administrator account reactivation",
            )
            telegram_id = user.telegram_id
        try:
            await bot.send_message(telegram_id, "Hisobingiz administrator tomonidan faollashtirildi.")
        except TelegramAPIError:
            pass
        await show_user_detail(callback, user_id)
        return

    if data.startswith("admin:payments:pending:"):
        page_text = data.removeprefix("admin:payments:pending:")
        if not page_text.isdecimal():
            await edit_or_answer(callback, "Sahifa raqami noto‘g‘ri.", admin_menu())
            return
        await show_payment_page(callback, status="pending", page=int(page_text))
        return

    if data == "admin:payments:history":
        await edit_or_answer(
            callback,
            "To‘lovlar tarixini holati bo‘yicha tanlang.",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Tasdiqlangan", callback_data="admin:payments:approved:0"),
                        InlineKeyboardButton(text="Rad etilgan", callback_data="admin:payments:rejected:0"),
                    ],
                    [InlineKeyboardButton(text="Kutilayotgan", callback_data="admin:payments:pending:0")],
                    [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")],
                ]
            ),
        )
        return

    if data.startswith(("admin:payments:approved:", "admin:payments:rejected:")):
        parts = data.split(":")
        if len(parts) != 4 or not parts[3].isdecimal():
            await edit_or_answer(callback, "Sahifa raqami noto‘g‘ri.", admin_menu())
            return
        await show_payment_page(callback, status=parts[2], page=int(parts[3]))
        return

    if data.startswith("admin:payment:detail:"):
        payment_id = safe_int(data.removeprefix("admin:payment:detail:"))
        if payment_id is None:
            await edit_or_answer(callback, "To‘lov raqami noto‘g‘ri.", admin_menu())
        else:
            await show_payment_detail(callback, payment_id, bot)
        return

    if data.startswith("admin:payment:approve:"):
        payment_id = safe_int(data.removeprefix("admin:payment:approve:"))
        if payment_id is None:
            await edit_or_answer(callback, "To‘lov raqami noto‘g‘ri.", admin_menu())
            return
        try:
            async with SessionFactory() as session, session.begin():
                payment, newly_approved = await approve_payment(
                    session,
                    payment_id=payment_id,
                    admin_telegram_id=callback.from_user.id,
                )
                user = await session.get(User, payment.user_id)
                report = await session.get(AssessmentReport, payment.report_id)
                user_telegram_id = user.telegram_id if user else None
                report_text = report.report_text if report else None
        except ValueError as error:
            await edit_or_answer(callback, str(error), admin_menu())
            return
        await edit_or_answer(callback, f"To‘lov #{payment_id} tasdiqlandi. Hisobotga kirish berildi.", admin_menu())
        if newly_approved and user_telegram_id and report_text:
            try:
                await bot.send_message(user_telegram_id, "To‘lov tasdiqlandi. Hisobotingiz:\n\n" + report_text)
            except TelegramAPIError as error:
                logger.warning("Report release notification failed (%s).", type(error).__name__)
        return

    if data.startswith("admin:payment:reject:") and not data.startswith("admin:payment:reject-confirm:"):
        payment_id = safe_int(data.removeprefix("admin:payment:reject:"))
        if payment_id is None:
            await edit_or_answer(callback, "To‘lov raqami noto‘g‘ri.", admin_menu())
        else:
            await edit_or_answer(
                callback,
                f"To‘lov #{payment_id} rad etilsinmi? Bu amal foydalanuvchiga xabar yuboradi.",
                payment_rejection_confirmation(payment_id),
            )
        return

    if data.startswith("admin:payment:reject-confirm:"):
        payment_id = safe_int(data.removeprefix("admin:payment:reject-confirm:"))
        if payment_id is None:
            await edit_or_answer(callback, "To‘lov raqami noto‘g‘ri.", admin_menu())
            return
        try:
            async with SessionFactory() as session, session.begin():
                payment = await reject_payment(
                    session,
                    payment_id=payment_id,
                    admin_telegram_id=callback.from_user.id,
                    reason="Administrator tomonidan tekshirilib rad etildi.",
                )
                user = await session.get(User, payment.user_id)
                telegram_id = user.telegram_id if user else None
        except ValueError as error:
            await edit_or_answer(callback, str(error), admin_menu())
            return
        await edit_or_answer(callback, f"To‘lov #{payment_id} rad etildi. Amal jurnali saqlandi.", admin_menu())
        if telegram_id:
            try:
                await bot.send_message(
                    telegram_id,
                    f"Chek bo‘yicha to‘lov tasdiqlanmadi. Qayta tekshirib yangi chek yuboring yoki "
                    f"{ADMIN_CONTACT} bilan bog‘laning.",
                )
            except TelegramAPIError:
                pass
        return

    if data == "admin:tests":
        await show_test_management(callback)
        return

    if data.startswith("admin:test-toggle:"):
        slug = data.removeprefix("admin:test-toggle:")
        if slug not in TEST_NAMES:
            await edit_or_answer(callback, "Test turi noto‘g‘ri.", admin_menu())
            return
        async with SessionFactory() as session, session.begin():
            category = await session.get(TestCategory, slug)
            if category is None:
                await edit_or_answer(callback, "Test topilmadi.", admin_menu())
                return
            await set_category_enabled(
                session,
                slug=slug,
                enabled=not category.is_enabled,
                admin_telegram_id=callback.from_user.id,
            )
        await show_test_management(callback)
        return

    if data == "admin:test-stats":
        async with SessionFactory() as session:
            rows = await stats_by_test(session)
        lines = ["📈 Test statistikasi"]
        if not rows:
            lines.append("Hozircha yakunlangan test yo‘q.")
        for row in rows:
            lines.append(
                f"\n{TEST_NAMES.get(row['category_slug'], row['category_slug'])} · "
                f"yosh {row['age_band']}: {row['completed']} ta yakunlangan"
                f" · o‘rtacha {row['average_score']}/{row['average_max']}"
            )
        await edit_or_answer(callback, "\n".join(lines)[:3900], admin_menu())
        return

    if data == "admin:settings":
        async with SessionFactory() as session:
            enabled_categories = list(
                await session.scalars(
                    select(TestCategory).where(TestCategory.is_enabled.is_(True)).order_by(TestCategory.sort_order)
                )
            )
        text = (
            "⚙️ Bot sozlamalari\n\n"
            f"Hisobot narxi: {format_uzs(PRICE_PER_REPORT_UZS)}\n"
            f"To‘lov qabul qiluvchi: {PAYMENT_RECIPIENT}\n"
            f"Karta raqami: {PAYMENT_CARD_NUMBER}\n"
            f"Administrator aloqa: {ADMIN_CONTACT}\n"
            f"ADMIN_IDS dagi vakolatli ID lar: {len(settings.admin_ids)}\n"
            f"Faol testlar: {len(enabled_categories)} / {len(TEST_NAMES)}\n\n"
            "Karta ma’lumoti faqat vakolatli administratorga ko‘rsatiladi; u loglarga yozilmaydi."
        )
        await edit_or_answer(callback, text, admin_menu())
        return

    if data == "admin:broadcast":
        await edit_or_answer(
            callback,
            "📢 Xabar yuborish\n\n"
            "Xizmat e’loni barcha faol va xizmat xabarlariga rozilik bergan foydalanuvchilarga yuboriladi. "
            "Reklama faqat reklama xabarlariga alohida rozilik berganlarga yuboriladi.",
            broadcast_start_keyboard(),
        )
        return

    if data.startswith("admin:broadcast:start:"):
        audience = data.removeprefix("admin:broadcast:start:")
        if audience not in {"service", "promotional"}:
            await edit_or_answer(callback, "Xabar turi noto‘g‘ri.", broadcast_start_keyboard())
            return
        async with SessionFactory() as session, session.begin():
            await set_state(
                session,
                callback.from_user.id,
                "admin_broadcast_message",
                {"audience": audience},
            )
        await edit_or_answer(
            callback,
            "Yuboriladigan matnni yozing yoki rasm yuborib, unga izoh qo‘shing. "
            "Matnni oldindan ko‘rib chiqib, tasdiqlash talab qilinadi. Bekor qilish uchun /cancel.",
        )
        return

    if data == "admin:broadcast:edit":
        state, payload = await load_state(callback.from_user.id)
        if state != "admin_broadcast_confirm":
            await edit_or_answer(callback, "Qoralama topilmadi. Yangi xabar boshlang.", broadcast_start_keyboard())
            return
        async with SessionFactory() as session, session.begin():
            await set_state(session, callback.from_user.id, "admin_broadcast_message", {
                "audience": payload.get("audience"),
            })
        await edit_or_answer(callback, "Yangi matnni yozing yoki rasm yuboring.")
        return

    if data == "admin:broadcast:cancel":
        async with SessionFactory() as session, session.begin():
            await clear_state(session, callback.from_user.id)
            session.add(
                AdminAction(
                    actor_telegram_id=callback.from_user.id,
                    action="broadcast_cancelled",
                )
            )
        await edit_or_answer(callback, "Xabar yuborish bekor qilindi. Hech kimga xabar yuborilmadi.", admin_menu())
        return

    if data == "admin:broadcast:confirm":
        state, payload = await load_state(callback.from_user.id)
        if state != "admin_broadcast_confirm" or not payload.get("text"):
            await edit_or_answer(callback, "Tasdiqlash uchun qoralama topilmadi.", broadcast_start_keyboard())
            return
        try:
            async with SessionFactory() as session, session.begin():
                job, eligible_count = await create_broadcast_job(
                    session,
                    audience=payload["audience"],
                    message_text=payload["text"],
                    photo_file_id=payload.get("photo_file_id"),
                    entities_json=payload.get("entities_json"),
                    caption_entities_json=payload.get("caption_entities_json"),
                    initiated_by_telegram_id=callback.from_user.id,
                )
                job_id = job.id
                await clear_state(session, callback.from_user.id)
        except ValueError as error:
            await edit_or_answer(callback, str(error), broadcast_start_keyboard())
            return
        await edit_or_answer(
            callback,
            f"Broadcast #{job_id} yaratildi. {eligible_count} ta mos foydalanuvchi navbatga qo‘shildi. "
            "Yuborish fon rejimida davom etadi.",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📊 View broadcast results", callback_data=f"admin:broadcast:results:{job_id}")],
                    [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")],
                ]
            ),
        )
        return

    if data == "admin:broadcast:results:list":
        async with SessionFactory() as session:
            jobs = list(
                await session.scalars(
                    select(BroadcastJob).order_by(BroadcastJob.created_at.desc()).limit(10)
                )
            )
        buttons = [
            [InlineKeyboardButton(
                text=f"#{job.id} · {job.audience} · {job.status}",
                callback_data=f"admin:broadcast:results:{job.id}",
            )]
            for job in jobs
        ]
        buttons.append([InlineKeyboardButton(text="🔙 Broadcast", callback_data="admin:broadcast")])
        buttons.append([InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")])
        await edit_or_answer(callback, "📊 Oxirgi broadcast ishlari:", InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    if data.startswith("admin:broadcast:results:"):
        job_id = safe_int(data.removeprefix("admin:broadcast:results:"))
        if job_id is None:
            await edit_or_answer(callback, "Ish raqami noto‘g‘ri.", broadcast_start_keyboard())
        else:
            await show_broadcast_results(callback, job_id)
        return

    if data == "noop":
        return
    await edit_or_answer(callback, "Noma’lum administrator amali.", admin_menu())


async def show_test_management(callback: CallbackQuery) -> None:
    async with SessionFactory() as session:
        categories = list(
            await session.scalars(select(TestCategory).order_by(TestCategory.sort_order))
        )
        grouped = dict(
            (
                await session.execute(select(Question.category_slug, func.count(Question.id)).group_by(Question.category_slug))
            ).all()
        )
    await edit_or_answer(
        callback,
        "🧠 Testlarni boshqarish\nTestni bosib yoqish yoki vaqtincha o‘chirish mumkin.",
        category_toggle_keyboard(categories, {key: int(value) for key, value in grouped.items()}),
    )


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message()
async def handle_text_and_receipts(message: Message, bot: Bot) -> None:
    if message.from_user is None or not _is_private_chat(message):
        return
    telegram_id = message.from_user.id
    await get_active_user(telegram_id)
    state, payload = await load_state(telegram_id)
    if state is None:
        return

    if state.startswith("admin_") and not is_authorized_admin(telegram_id, settings.admin_ids):
        async with SessionFactory() as session, session.begin():
            await clear_state(session, telegram_id)
        await message.answer("Administrator ruxsati mavjud emas.")
        return

    if state == "awaiting_age":
        text = (message.text or "").strip()
        if not text.isdecimal() or not 7 <= int(text) <= 70:
            await message.answer("Yoshingizni 7 dan 70 gacha bo‘lgan butun son bilan kiriting.")
            return
        async with SessionFactory() as session, session.begin():
            user = await upsert_user(
                session,
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                age=int(text),
            )
            await clear_state(session, telegram_id)
            suspended = user.account_status == "suspended"
        if suspended:
            await message.answer(f"Hisobingiz vaqtincha to‘xtatilgan. {ADMIN_CONTACT} bilan bog‘laning.")
        else:
            await message.answer(
                "Ro‘yxatdan o‘tish yakunlandi. Test savollari yoshingizga mos tanlanadi.",
                reply_markup=user_main_menu(is_authorized_admin(telegram_id, settings.admin_ids)),
            )
        return

    if state == "awaiting_receipt":
        photo = message.photo[-1] if message.photo else None
        document = message.document
        if photo is None and document is None:
            await message.answer("Chek rasmini yoki PDF faylini yuboring. Bekor qilish uchun /cancel.")
            return
        if document is not None:
            allowed = document.mime_type in {"image/jpeg", "image/png", "application/pdf"}
            if not allowed:
                await message.answer("Faqat JPG, PNG rasm yoki PDF chekni qabul qilaman.")
                return
            file_id = document.file_id
            file_unique_id = document.file_unique_id
            receipt_kind = "document"
        else:
            file_id = photo.file_id
            file_unique_id = photo.file_unique_id
            receipt_kind = "photo"
        report_id = safe_int(str(payload.get("report_id", "")))
        if report_id is None:
            await message.answer("Hisobot raqami topilmadi. To‘lovni qaytadan boshlang.")
            return
        try:
            async with SessionFactory() as session, session.begin():
                payment = await submit_receipt(
                    session,
                    telegram_id=telegram_id,
                    report_id=report_id,
                    file_id=file_id,
                    file_unique_id=file_unique_id,
                    receipt_kind=receipt_kind,
                )
                payment_id = payment.id
                await clear_state(session, telegram_id)
                user = await get_user_by_telegram_id(session, telegram_id)
                user_name = " ".join(
                    part for part in [message.from_user.first_name, message.from_user.last_name] if part
                ) or "—"
                username = message.from_user.username or "—"
                user_id = user.id if user else None
                report = await session.get(AssessmentReport, payment.report_id)
                attempt = await session.get(TestAttempt, report.attempt_id) if report else None
                category = await session.get(TestCategory, attempt.category_slug) if attempt else None
                category_name = category.name_uz if category else "—"
        except ValueError as error:
            await message.answer(str(error))
            return
        await message.answer(
            f"Chek qabul qilindi. To‘lov #{payment_id} tekshirilgandan so‘ng hisobot ochiladi. "
            f"Bu odatda administrator ko‘rigini talab qiladi."
        )
        for admin_id in settings.admin_ids:
            caption = (
                f"💳 Yangi chek · to‘lov #{payment_id}\n"
                f"Foydalanuvchi #{user_id} · Telegram ID {telegram_id}\n"
                f"Ism: {user_name} · @{username}\n"
                f"Test: {category_name}\n"
                f"Summa: {format_uzs(PRICE_PER_REPORT_UZS)}"
            )
            try:
                if receipt_kind == "photo":
                    await bot.send_photo(
                        admin_id,
                        file_id,
                        caption=caption,
                        reply_markup=payment_review_keyboard(payment_id),
                    )
                else:
                    await bot.send_document(
                        admin_id,
                        file_id,
                        caption=caption,
                        reply_markup=payment_review_keyboard(payment_id),
                    )
            except TelegramAPIError as error:
                logger.warning("Payment review notification failed (%s).", type(error).__name__)
        return

    if state == "admin_user_search":
        search_term = (message.text or "").strip()
        if not search_term or len(search_term) > 100:
            await message.answer("Qidiruv uchun Telegram ID, username yoki ismni yuboring (1–100 belgi).")
            return
        async with SessionFactory() as session, session.begin():
            await set_state(
                session,
                telegram_id,
                "admin_user_search_results",
                {"search_term": search_term},
            )
        await render_users(message, page=0, search_term=search_term)
        return

    if state == "admin_suspend_reason":
        reason = (message.text or "").strip()
        user_id = payload.get("user_id")
        if not reason or len(reason) > 300 or not isinstance(user_id, int):
            await message.answer("Sababni 1–300 belgi bilan yuboring.")
            return
        async with SessionFactory() as session, session.begin():
            await set_state(
                session,
                telegram_id,
                "admin_suspend_confirm",
                {"user_id": user_id, "reason": reason},
            )
        await message.answer(
            f"Foydalanuvchi #{user_id} hisobini to‘xtatish sababi:\n{reason}\n\nTasdiqlaysizmi?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="⏸ Hisobni to‘xtatish",
                        callback_data=f"admin:user:suspend-confirm:{user_id}",
                    )],
                    [InlineKeyboardButton(text="Bekor qilish", callback_data="admin:menu")],
                ]
            ),
        )
        return

    if state == "admin_broadcast_message":
        audience = payload.get("audience")
        if audience not in {"service", "promotional"}:
            await message.answer("Xabar qoralamasi topilmadi. /admin orqali qayta boshlang.")
            return
        photo = message.photo[-1] if message.photo else None
        if photo is not None:
            text = message.caption or ""
            if not text.strip():
                await message.answer("Rasmga qisqa izoh qo‘shing yoki matnli xabar yuboring.")
                return
            if len(text) > 1024:
                await message.answer("Rasm izohi 1024 belgidan oshmasligi kerak.")
                return
            new_payload = {
                "audience": audience,
                "text": text,
                "photo_file_id": photo.file_id,
                "entities_json": None,
                "caption_entities_json": entity_data(message.caption_entities),
            }
        else:
            text = message.text or ""
            if not text.strip():
                await message.answer("Matn yoki rasmli izoh yuboring.")
                return
            if len(text) > 4000:
                await message.answer("Xabar 4000 belgidan oshmasligi kerak.")
                return
            new_payload = {
                "audience": audience,
                "text": text,
                "photo_file_id": None,
                "entities_json": entity_data(message.entities),
                "caption_entities_json": None,
            }
        async with SessionFactory() as session, session.begin():
            await set_state(session, telegram_id, "admin_broadcast_confirm", new_payload)
        await message.answer("Xabar ko‘rinishi (yuboriladigan matn aynan shu):")
        try:
            if photo is not None:
                await bot.send_photo(
                    telegram_id,
                    photo.file_id,
                    caption=text,
                    caption_entities=message.caption_entities or None,
                )
            else:
                await bot.send_message(telegram_id, text, entities=message.entities or None)
        except TelegramAPIError as error:
            logger.warning("Broadcast preview failed (%s).", type(error).__name__)
            await message.answer("Xabarni ko‘rib chiqib bo‘lmadi; tahrirlab qayta yuboring.")
            return
        await message.answer(
            "Tasdiqlashdan keyin xabar mos va rozilik bergan foydalanuvchilarga navbat bilan yuboriladi. "
            "Davom etasizmi?",
            reply_markup=broadcast_confirmation_keyboard(),
        )
        return


async def setup_bot_commands(bot: Bot) -> None:
    from aiogram.types import BotCommand

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Botni boshlash"),
            BotCommand(command="menu", description="Bosh menyu"),
            BotCommand(command="admin", description="Administrator paneli"),
            BotCommand(command="id", description="O‘z Telegram ID raqamingizni ko‘rish"),
            BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
        ]
    )
