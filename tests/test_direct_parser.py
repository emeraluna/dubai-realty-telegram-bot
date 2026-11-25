from scrapers.direct import parse_listing_html
from services.lookup_request import LookupRequest


def test_parse_next_data_contact() -> None:
    html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"listing":{"buildingName":"Ocean Heights","community":"Dubai Marina","ownerName":"Ali Ahmed","ownerPhone":"+971501112233"}}}}
    </script>
    </body></html>
    """
    req = LookupRequest(
        source="propertyfinder",
        external_id="123",
        raw_input="https://www.propertyfinder.ae/en/plp/buy/unit-123.html",
    )
    payload = parse_listing_html(html, req)
    assert payload.building == "Ocean Heights"
    assert payload.community == "Dubai Marina"
    assert payload.owner_name == "Ali Ahmed"
    assert payload.owner_phone == "+971501112233"


def test_parse_json_ld_contact() -> None:
    html = """
    <script type="application/ld+json">
    {"@type":"Apartment","name":"Studio","contactPoint":{"name":"Sara","telephone":"+971509998877"}}
    </script>
    """
    req = LookupRequest(
        source="bayut",
        external_id="9",
        raw_input="https://www.bayut.com/property/details-9.html",
    )
    payload = parse_listing_html(html, req)
    assert payload.owner_name == "Sara"
    assert payload.owner_phone == "+971509998877"