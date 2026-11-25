import asyncio
import sys

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import setup_routers
from bot.middlewares.acl import AllowedUsersMiddleware
from config import configure_logging, get_settings
from bot.services.owner_resolve_worker import start_owner_resolve_worker
from db.bootstrap import run_migrations, verify_database
from db.session import dispose_engine

log = structlog.get_logger(__name__)


async def _run() -> None:
    settings = get_settings()
    await verify_database()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    root = setup_routers()
    root.message.middleware(AllowedUsersMiddleware())
    root.callback_query.middleware(AllowedUsersMiddleware())
    dp.include_router(root)
    log.info("bot.starting", allowed_ids=len(settings.allowed_telegram_ids))
    worker_task = start_owner_resolve_worker(bot)
    try:
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        await dispose_engine()


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        run_migrations()
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("bot.stopped")
        sys.exit(0)


if __name__ == "__main__":
    run()