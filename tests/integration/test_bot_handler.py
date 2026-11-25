from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers import lookup
from bot.services.lookup_orchestrator import LookupOutcome
from db.models import Listing
from services.lookup_request import LookupRequest


@pytest.mark.asyncio
async def test_lookup_handler_with_mocked_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = Listing(
        id=99,
        source="bayut",
        building="Test Tower",
        community="JVC",
        developer="DevCo",
        unit_number="101",
        floor="1",
        size_sqft=900.0,
        plot_number="P-1",
        permit_number="711111111111",
        permit_status="active",
        owner_name="Test Owner",
        owner_phone="+971500000777",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        lookup_count=1,
        raw_payload={},
    )
    request = LookupRequest(
        source="bayut",
        external_id="7777777",
        raw_input="https://www.bayut.com/property/details-7777777.html",
    )
    outcome = LookupOutcome(listing=listing, cache_hit=False, request=request)

    mock_run = AsyncMock(return_value=outcome)
    monkeypatch.setattr(lookup._orchestrator, "run", mock_run)

    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.text = request.raw_input
    message.answer = AsyncMock(return_value=status_message)

    await lookup.handle_lookup_text(message)

    mock_run.assert_awaited_once_with(
        telegram_user_id=12345,
        text=request.raw_input,
        force_refresh=False,
    )
    status_message.edit_text.assert_awaited()
    edit_args = status_message.edit_text.await_args
    assert edit_args is not None
    body = edit_args.args[0]
    assert "Test Tower" in body
    assert "Test Owner" in body
    assert "+971500000777" in body
    assert edit_args.kwargs.get("parse_mode") == "HTML"
    assert edit_args.kwargs.get("reply_markup") is not None