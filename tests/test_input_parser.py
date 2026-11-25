import pytest

from services.input_parser import InputParseError, parse_lookup_input


@pytest.mark.parametrize(
    "raw,expected_id",
    [
        (
            "https://www.propertyfinder.ae/en/plp/buy/apartment-for-sale-dubai-12345678.html",
            "12345678",
        ),
        (
            "https://www.propertyfinder.ae/en/plp/buy/villa-999.html?foo=bar",
            "999",
        ),
        (
            "https://m.propertyfinder.ae/en/plp/rent/apartment-55555555.html/",
            "55555555",
        ),
        (
            "www.propertyfinder.ae/en/plp/buy/apartment-42424242.html",
            "42424242",
        ),
        (
            "  https://propertyfinder.ae/en/plp/buy/flat-10001.html  ",
            "10001",
        ),
    ],
)
def test_propertyfinder_urls(raw: str, expected_id: str) -> None:
    req = parse_lookup_input(raw, permit_min_length=10, permit_max_length=15)
    assert req.source == "propertyfinder"
    assert req.external_id == expected_id
    assert req.raw_input == raw


@pytest.mark.parametrize(
    "raw,expected_id",
    [
        (
            "https://www.bayut.com/property/details-1234567.html",
            "1234567",
        ),
        (
            "https://www.bayut.com/property/details-8888888.html?utm_source=telegram",
            "8888888",
        ),
        (
            "https://m.bayut.com/property/details-42.html/",
            "42",
        ),
        (
            "bayut.com/property/details-7777777.html",
            "7777777",
        ),
    ],
)
def test_bayut_urls(raw: str, expected_id: str) -> None:
    req = parse_lookup_input(raw, permit_min_length=10, permit_max_length=15)
    assert req.source == "bayut"
    assert req.external_id == expected_id
    assert req.raw_input == raw


@pytest.mark.parametrize(
    "raw,expected_id",
    [
        ("7123456789", "7123456789"),
        (" 7123456789 ", "7123456789"),
        ("permit:7123456789", "7123456789"),
        ("PERMIT: 712345678901", "712345678901"),
        ("permit:71234567890123", "71234567890123"),
    ],
)
def test_trakheesi_permit(raw: str, expected_id: str) -> None:
    req = parse_lookup_input(raw, permit_min_length=10, permit_max_length=15)
    assert req.source == "trakheesi"
    assert req.external_id == expected_id
    assert req.raw_input == raw


def test_propertyfinder_before_bayut_lookalike() -> None:
    raw = "https://www.propertyfinder.ae/en/plp/buy/unit-10101010.html"
    req = parse_lookup_input(raw, permit_min_length=10, permit_max_length=15)
    assert req.source == "propertyfinder"


def test_numeric_url_not_treated_as_permit() -> None:
    raw = "https://www.bayut.com/property/details-1234567890.html"
    req = parse_lookup_input(raw, permit_min_length=10, permit_max_length=15)
    assert req.source == "bayut"
    assert req.external_id == "1234567890"


def test_empty_input_raises() -> None:
    with pytest.raises(InputParseError):
        parse_lookup_input("   ", permit_min_length=10, permit_max_length=15)


def test_invalid_permit_length_raises() -> None:
    with pytest.raises(InputParseError):
        parse_lookup_input("12345", permit_min_length=10, permit_max_length=15)


def test_unknown_host_raises() -> None:
    with pytest.raises(InputParseError):
        parse_lookup_input("https://example.com/listing/1.html", permit_min_length=10, permit_max_length=15)


def test_url_without_listing_id_raises() -> None:
    with pytest.raises(InputParseError):
        parse_lookup_input(
            "https://www.propertyfinder.ae/en/search",
            permit_min_length=10,
            permit_max_length=15,
        )


def test_permit_checked_after_urls_when_slashes_present() -> None:
    with pytest.raises(InputParseError):
        parse_lookup_input("permit:7123456789/extra", permit_min_length=10, permit_max_length=15)