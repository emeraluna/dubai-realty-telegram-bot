from scrapers.madmoun_html import parse_madmoun_visible_text

SAMPLE = """
Real Estate Permit Card
This Listing has been verified by Dubai Land Department.
Listing Details
Transaction Number
153343
Listing Number

End Date
31/12/2026
Authority Information
License #
1106530
Authority Name
STERLING BOULEVARD REAL ESTATE L.L.C
Broker Information
#
55786
Name
ALEJANDRO VEGA GONZALEZ
Email
ale.vg.gon@gmail.com
Mobile
971501046096
Property Details
Property Name
Binghatti Grove
"""


def test_parse_madmoun_visible_text() -> None:
    parsed = parse_madmoun_visible_text(SAMPLE)
    assert parsed.get("verified") is True
    auth = parsed["sections"]["Authority Information"]
    assert auth["License #"] == "1106530"
    broker = parsed["sections"]["Broker Information"]
    assert broker["Mobile"] == "971501046096"