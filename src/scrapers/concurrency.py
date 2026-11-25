from __future__ import annotations

import asyncio

from config import get_settings
from services.lookup_request import LookupSource


class SourceConcurrency:
    def __init__(self) -> None:
        self._limits: dict[LookupSource, int] = {}
        self._semaphores: dict[LookupSource, asyncio.Semaphore] = {}

    def _limit_for(self, source: LookupSource) -> int:
        if source in self._limits:
            return self._limits[source]
        settings = get_settings()
        limits = {
            "propertyfinder": settings.extractor_concurrency_propertyfinder,
            "bayut": settings.extractor_concurrency_bayut,
            "trakheesi": settings.extractor_concurrency_trakheesi,
        }
        self._limits[source] = limits[source]
        return self._limits[source]

    def semaphore(self, source: LookupSource) -> asyncio.Semaphore:
        if source not in self._semaphores:
            self._semaphores[source] = asyncio.Semaphore(self._limit_for(source))
        return self._semaphores[source]

    async def run(self, source: LookupSource, coro_factory):
        async with self.semaphore(source):
            return await coro_factory()


source_concurrency = SourceConcurrency()