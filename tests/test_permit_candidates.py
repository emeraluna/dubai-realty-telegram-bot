from services.permit_candidates import collect_permit_candidates, collect_validation_urls


def test_collect_validation_url_from_rera() -> None:
    raw = {
        "direct": {
            "rera": {
                "issued_license_number": "1106530",
                "permit_validation_url": "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation?khevJujtDig=abc",
            }
        }
    }
    urls = collect_validation_urls(raw)
    assert len(urls) == 1
    permits = collect_permit_candidates(raw)
    assert "1106530" in permits