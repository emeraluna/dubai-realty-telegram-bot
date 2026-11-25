from aiogram import F, Router
from aiogram.enums import ChatType

from bot.handlers import callbacks, commands, export_stats, import_handler, lookup


def setup_routers() -> Router:
    root = Router(name="root")
    root.message.filter(F.chat.type == ChatType.PRIVATE)
    root.include_router(commands.router)
    root.include_router(export_stats.router)
    root.include_router(lookup.router)
    root.include_router(callbacks.router)
    root.include_router(import_handler.router)
    return root