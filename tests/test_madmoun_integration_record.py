from scrapers.actor_maps import MadmounBrokerRecord, MadmounIntegrationRecord


def test_madmoun_maps_license_not_card_holder_as_owner() -> None:
    record = MadmounIntegrationRecord.model_validate(
        {
            "CardHolderNameEn": "Broker Person",
            "CardHolderMobile": "+971501046096",
            "LicenseNumber": "1106530",
            "PermitNumber": "153343",
        }
    )
    payload = record.to_listing_payload()
    assert payload.owner_name is None
    assert payload.owner_phone is None
    assert payload.permit_number == "1106530"


def test_madmoun_broker_record() -> None:
    broker = MadmounBrokerRecord.model_validate(
        {"CardHolderNameEn": "Broker Person", "CardHolderMobile": "971501046096", "LicenseNumber": "1106530"}
    )
    assert broker.broker_name_en == "Broker Person"
    assert broker.broker_phone == "971501046096"