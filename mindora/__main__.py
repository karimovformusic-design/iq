from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import text

from mindora.broadcast_worker import run_broadcast_worker
from mindora.db import SessionFactory, dispose_engine
from mindora.handlers import router, setup_bot_commands
from mindora.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mindora")


async def healthz(_request: web.Request) -> web.Response:
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return web.json_response({"status": "ok"})
    except Exception as error:
        logger.warning("Health check failed (%s).", type(error).__name__)
        return web.json_response({"status": "unavailable"}, status=503)


async def run() -> None:
    if settings.telegram_bot_token is None:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be configured before starting the bot.")
    # Evaluate here so invalid or non-numeric ADMIN_IDS fails closed at startup.
    _ = settings.admin_ids

    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=None),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    health_app = web.Application()
    health_app.router.add_get("/healthz", healthz)
    health_runner = web.AppRunner(health_app, access_log=None)
    await health_runner.setup()
    health_site = web.TCPSite(health_runner, host="0.0.0.0", port=settings.port)
    await health_site.start()

    worker = asyncio.create_task(run_broadcast_worker(bot), name="persistent-broadcast-worker")
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        await bot.get_me()
        await setup_bot_commands(bot)
        logger.info("MINDORA bot connected; polling Telegram updates.")
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await health_runner.cleanup()
        await bot.session.close()
        await dispose_engine()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
