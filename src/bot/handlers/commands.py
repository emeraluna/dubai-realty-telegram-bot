from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Dubai realty lookup bot.\n\n"
        "Send a Property Finder URL, Bayut URL, or Trakheesi permit number.\n"
        "Commands: /help, /export, /stats"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Input</b>\n"
        "• Property Finder listing URL\n"
        "• Bayut listing URL\n"
        "• Trakheesi permit (digits or permit:XXXX)\n\n"
        "<b>Commands</b>\n"
        "/export — CSV of your archive\n"
        "/stats — lookup counts and cache savings",
        parse_mode="HTML",
    )