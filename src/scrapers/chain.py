from __future__ import annotations

import structlog

from config import get_settings
from scrapers.apify import ApifyExtractor
from scrapers.base import BaseExtractor
from scrapers.dld_phone import DldPhoneExtractor
from scrapers.direct import DirectParserExtractor
from scrapers.propertyfinder_api import fetch_propertyfinder_listing
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload, merge_payloads
from scrapers.scrapeforge import ScrapeForgeExtractor
from scrapers.trakheesi import TrakheesiExtractor
from services.lookup_request import LookupRequest, LookupSource
from services.owner_enrichment import enrich_owner_from_dld

log = structlog.get_logger(__name__)

class PropertyFinderApiExtractor(BaseExtractor):
    name = "propertyfinder_api"

    def supports(self, req: LookupRequest) -> bool:
        return req.source == "propertyfinder"

    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        return await fetch_propertyfinder_listing(req)


EXTRACTOR_REGISTRY: dict[str, type[BaseExtractor]] = {
    "propertyfinder_api": PropertyFinderApiExtractor,
    "apify": ApifyExtractor,
    "scrapeforge": ScrapeForgeExtractor,
    "direct": DirectParserExtractor,
    "trakheesi": TrakheesiExtractor,
    "dld_phone": DldPhoneExtractor,
}


def _parse_priority(raw: str) -> list[str]:
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


class ExtractorChain:
    def __init__(self, extractors: list[BaseExtractor] | None = None) -> None:
        self._extractors = extractors

    def _priority(self, source: LookupSource) -> list[str]:
        settings = get_settings()
        if source == "propertyfinder":
            return _parse_priority(settings.extractor_priority_propertyfinder)
        if source == "bayut":
            return _parse_priority(settings.extractor_priority_bayut)
        if source == "dld_phone":
            return ["dld_phone"]
        return _parse_priority(settings.extractor_priority_trakheesi)

    def _build(self, req: LookupRequest) -> list[BaseExtractor]:
        if self._extractors is not None:
            return [ext for ext in self._extractors if ext.supports(req)]
        names = self._priority(req.source)
        built: list[BaseExtractor] = []
        for name in names:
            cls = EXTRACTOR_REGISTRY.get(name)
            if cls is None:
                continue
            built.append(cls())
        if req.source == "trakheesi" and not built:
            built.append(TrakheesiExtractor())
        if req.source == "dld_phone" and not built:
            built.append(DldPhoneExtractor())
        return built

    async def extract(self, req: LookupRequest) -> ListingPayload:
        extractors = self._build(req)
        if not extractors:
            raise ExtractionError(
                code="no_extractors",
                message="no extractors configured for source",
                extractor="chain",
                source=req.source,
            )

        primary: ListingPayload | None = None
        last_error: ExtractionError | None = None

        for index, extractor in enumerate(extractors):
            try:
                payload = await extractor.fetch(req)
            except ExtractionError as exc:
                last_error = exc
                log.warning(
                    "extractor.chain.failed",
                    extractor=extractor.name,
                    source=req.source,
                    code=exc.code,
                )
                continue

            if primary is None:
                primary = payload
                log.info(
                    "extractor.chain.primary",
                    extractor=extractor.name,
                    source=req.source,
                )
            else:
                primary = merge_payloads(primary, payload)
                log.info(
                    "extractor.chain.merged",
                    extractor=extractor.name,
                    source=req.source,
                    missing=sorted(primary.missing_enrichment_fields()),
                )

            if index == 0 and not primary.needs_enrichment():
                break

            if primary is not None and not primary.missing_enrichment_fields():
                break

        if primary is None:
            raise last_error or ExtractionError(
                code="all_extractors_failed",
                message="all extractors failed",
                extractor="chain",
                source=req.source,
            )

        if req.source in ("propertyfinder", "bayut"):
            primary = await enrich_owner_from_dld(primary)

        return primary