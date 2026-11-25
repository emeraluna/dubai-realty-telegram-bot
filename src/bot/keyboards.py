from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def listing_actions_keyboard(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Refresh", callback_data=f"refresh:{listing_id}"),
                InlineKeyboardButton(text="Export this record", callback_data=f"export_one:{listing_id}"),
            ]
        ]
    )