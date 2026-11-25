import pytest

from scrapers.chain import ExtractorChain
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest


class _StubExtractor:
    def __init__(self, name: str, payload: ListingPayload | None, error: ExtractionError | None = None) -> None:
        self.name = name
        self._payload = payload
        self._error = error

    def supports(self, req: LookupRequest) -> bool:
        return True

    async def fetch(self, req: LookupRequest) -> ListingPayload:
        if self._error:
            raise self._error
        assert self._payload is not None
        return self._payload


@pytest.mark.asyncio
async def test_chain_merges_owner_from_secondary() -> None:
    req = LookupRequest(
        source="propertyfinder",
        external_id="123",
        raw_input="https://www.propertyfinder.ae/en/plp/buy/u-123.html",
    )
    primary = ListingPayload(source="propertyfinder", building="Tower", owner_name=None, owner_phone=None)
    secondary = ListingPayload(
        source="propertyfinder",
        owner_name="Merged Owner",
        owner_phone="+971500000444",
    )
    chain = ExtractorChain(extractors=[_StubExtractor("a", primary), _StubExtractor("b", secondary)])
    result = await chain.extract(req)
    assert result.building == "Tower"
    assert result.owner_name == "Merged Owner"
    assert result.owner_phone == "+971500000444"


@pytest.mark.asyncio
async def test_chain_stops_when_complete_after_primary() -> None:
    req = LookupRequest(
        source="bayut",
        external_id="1",
        raw_input="https://www.bayut.com/property/details-1.html",
    )
    primary = ListingPayload(
        source="bayut",
        unit_number="101",
        floor="10",
        building="X",
        community="Y",
        developer="Dev",
        size_sqft=1200.0,
        plot_number="P1",
        permit_number="1",
        permit_status="ok",
        owner_name="A",
        owner_phone="B",
    )
    calls = 0

    class _FailIfCalled(_StubExtractor):
        async def fetch(self, req: LookupRequest) -> ListingPayload:
            nonlocal calls
            calls += 1
            return await super().fetch(req)

    chain = ExtractorChain(
        extractors=[_StubExtractor("a", primary), _FailIfCalled("b", ListingPayload(owner_name="Z"))]
    )
    result = await chain.extract(req)
    assert result.building == "X"
    assert calls == 0


@pytest.mark.asyncio
async def test_chain_raises_when_all_fail() -> None:
    req = LookupRequest(source="trakheesi", external_id="7123456789", raw_input="7123456789")
    chain = ExtractorChain(
        extractors=[
            _StubExtractor(
                "a",
                None,
                ExtractionError(code="x", message="fail", extractor="a", source="trakheesi"),
            )
        ]
    )
    with pytest.raises(ExtractionError):
        await chain.extract(req)