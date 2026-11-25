from __future__ import annotations

from abc import ABC, abstractmethod

import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest

log = structlog.get_logger(__name__)


class BaseExtractor(ABC):
    name: str

    @abstractmethod
    def supports(self, req: LookupRequest) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        raise NotImplementedError

    async def fetch(self, req: LookupRequest) -> ListingPayload:
        if not self.supports(req):
            raise ExtractionError(
                code="unsupported",
                message="extractor does not support request",
                extractor=self.name,
                source=req.source,
            )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
            reraise=True,
        ):
            with attempt:
                try:
                    payload = await self._fetch(req)
                    log.info(
                        "extractor.success",
                        extractor=self.name,
                        source=req.source,
                        external_id=req.external_id,
                    )
                    return payload
                except ExtractionError:
                    raise
                except Exception as exc:
                    log.warning(
                        "extractor.attempt_failed",
                        extractor=self.name,
                        source=req.source,
                        attempt=attempt.retry_state.attempt_number,
                        error=str(exc),
                    )
                    if attempt.retry_state.attempt_number >= 3:
                        raise ExtractionError(
                            code="fetch_failed",
                            message=str(exc),
                            extractor=self.name,
                            source=req.source,
                        ) from exc
                    raise
        raise ExtractionError(
            code="fetch_failed",
            message="exhausted retries",
            extractor=self.name,
            source=req.source,
        )