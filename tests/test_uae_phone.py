from services.input_parser import parse_lookup_input
from services.uae_phone import canonical_uae_mobile, is_uae_mobile_input


def test_canonical_mobile() -> None:
    assert canonical_uae_mobile("+971521149496") == "971521149496"
    assert canonical_uae_mobile("0521149496") == "971521149496"


def test_parse_dld_phone_input() -> None:
    req = parse_lookup_input("+971521149496")
    assert req.source == "dld_phone"
    assert req.external_id == "971521149496"


def test_permit_not_phone() -> None:
    assert is_uae_mobile_input("1106530") is False