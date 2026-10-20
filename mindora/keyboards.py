from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from mindora.constants import TEST_NAMES


def user_main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🧠 Test topshirish", callback_data="user:test-list")],
        [InlineKeyboardButton(text="📄 Hisobotlarim", callback_data="user:reports")],
        [InlineKeyboardButton(text="🔔 Xabar sozlamalari", callback_data="user:notifications")],
        [InlineKeyboardButton(text="❌ Joriy amalni bekor qilish", callback_data="user:cancel-current")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛡 Admin panel", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_menu() -> InlineKeyboardMarkup:
    labels = [
        ("📊 Dashboard", "admin:dashboard"),
        ("👥 All Users", "admin:users:page:0"),
        ("🔍 Search User", "admin:users:search"),
        ("📢 Broadcast Message", "admin:broadcast"),
        ("💳 Pending Payments", "admin:payments:pending:0"),
        ("📋 Payment History", "admin:payments:history"),
        ("🧠 Test Management", "admin:tests"),
        ("📈 Test Statistics", "admin:test-stats"),
        ("⚙️ Bot Settings", "admin:settings"),
        ("🔙 Back to Main Menu", "user:menu"),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=callback)]
            for label, callback in labels
        ]
    )


def test_categories(categories) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=category.name_uz,
                callback_data=f"user:test-start:{category.slug}",
            )
        ]
        for category in categories
    ]
    rows.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="user:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def question_options(attempt_id: int, position: int, options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=option[:60],
                callback_data=f"test:answer:{attempt_id}:{position}:{index}",
            )
        ]
        for index, option in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def page_controls(
    *,
    namespace: str,
    page: int,
    total: int,
    page_size: int,
    back_callback: str,
    search: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    total_pages = max(1, (total + page_size - 1) // page_size)
    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{namespace}:{page - 1}")
        )
    navigation.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{namespace}:{page + 1}")
        )
    rows.append(navigation)
    if search:
        rows.append([InlineKeyboardButton(text="🔍 Qidirish", callback_data="admin:users:search")])
    rows.append([InlineKeyboardButton(text="🔙 Admin menyu", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_detail_keyboard(user_id: int, status: str) -> InlineKeyboardMarkup:
    action = (
        InlineKeyboardButton(text="⏸ Hisobni to‘xtatish", callback_data=f"admin:user:suspend:{user_id}")
        if status == "active"
        else InlineKeyboardButton(text="▶️ Hisobni faollashtirish", callback_data=f"admin:user:reactivate:{user_id}")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 To‘lovlar", callback_data=f"admin:user:payments:{user_id}"),
                InlineKeyboardButton(text="🧠 Testlar", callback_data=f"admin:user:tests:{user_id}"),
            ],
            [action],
            [InlineKeyboardButton(text="🔙 Foydalanuvchilar", callback_data="admin:users:page:0")],
            [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")],
        ]
    )


def broadcast_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 Xizmat e’loni", callback_data="admin:broadcast:start:service")],
            [InlineKeyboardButton(text="📢 Reklama (rozilik berganlarga)", callback_data="admin:broadcast:start:promotional")],
            [InlineKeyboardButton(text="📊 View broadcast results", callback_data="admin:broadcast:results:list")],
            [InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")],
        ]
    )


def broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Hammaga yuborish", callback_data="admin:broadcast:confirm")],
            [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="admin:broadcast:edit")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:broadcast:cancel")],
            [InlineKeyboardButton(text="📊 View broadcast results", callback_data="admin:broadcast:results:list")],
        ]
    )


def payment_review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin:payment:approve:{payment_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin:payment:reject:{payment_id}"),
            ],
            [InlineKeyboardButton(text="🔙 Kutilayotgan to‘lovlar", callback_data="admin:payments:pending:0")],
        ]
    )


def payment_rejection_confirmation(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Ha, rad etish", callback_data=f"admin:payment:reject-confirm:{payment_id}")],
            [InlineKeyboardButton(text="Bekor qilish", callback_data=f"admin:payment:detail:{payment_id}")],
        ]
    )


def notification_settings(service: bool, promotional: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Xizmat xabarlari: {'yoqilgan' if service else 'o‘chirilgan'}",
                    callback_data="user:notifications:service",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Reklama xabarlari: {'yoqilgan' if promotional else 'o‘chirilgan'}",
                    callback_data="user:notifications:promotional",
                )
            ],
            [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="user:menu")],
        ]
    )


def category_toggle_keyboard(categories, question_counts: dict[str, int]) -> InlineKeyboardMarkup:
    rows = []
    for category in categories:
        status = "✅" if category.is_enabled else "⏸"
        count = question_counts.get(category.slug, 0)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {category.name_uz} · {count} savol",
                    callback_data=f"admin:test-toggle:{category.slug}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔙 Admin menyu", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_keyboard(report_id: int, released: bool) -> InlineKeyboardMarkup:
    if released:
        rows = [[InlineKeyboardButton(text="📄 Hisobotni ochish", callback_data=f"user:report:{report_id}")]]
    else:
        rows = [[InlineKeyboardButton(text="💳 Hisobot uchun to‘lov", callback_data=f"user:pay:{report_id}")]]
    rows.append([InlineKeyboardButton(text="🔙 Hisobotlarim", callback_data="user:reports")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def completed_test_choice_keyboard(report_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="☕ Qahva", callback_data=f"user:test:coffee:{report_id}")],
            [InlineKeyboardButton(text="🧠 Javoblarni bilish", callback_data=f"user:pay:{report_id}")],
        ]
    )


def delete_test_confirmation_keyboard(report_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"user:test:choice:{report_id}")],
            [InlineKeyboardButton(text="🗑 O‘chirib yuborish", callback_data=f"user:test:delete:{report_id}")],
        ]
    )
