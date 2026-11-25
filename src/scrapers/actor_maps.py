from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from scrapers.payload import ListingPayload


class ApifyListingRecord(BaseModel):
    """
    Assumed Apify actor output fields (property-finder / bayut scrapers):
    id, url, listingId, title, unitNumber, floor, building, community,
    developer, size, sizeSqft, plotNumber, permitNumber, permitStatus,
    ownerName, ownerPhone, landlordName, landlordPhone, permitNumber, raw.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str | None = Field(default=None, validation_alias=AliasChoices("id", "listingId"))
    url: str | None = None
    unit_number: str | None = Field(
        default=None, validation_alias=AliasChoices("unitNumber", "unit_number", "unit")
    )
    floor: str | None = None
    building: str | None = Field(
        default=None, validation_alias=AliasChoices("building", "buildingName", "tower")
    )
    community: str | None = Field(
        default=None, validation_alias=AliasChoices("community", "location", "neighborhood")
    )
    developer: str | None = Field(default=None, validation_alias=AliasChoices("developer", "developerName"))
    size_sqft: float | None = Field(
        default=None, validation_alias=AliasChoices("sizeSqft", "size_sqft", "size", "area")
    )
    plot_number: str | None = Field(default=None, validation_alias=AliasChoices("plotNumber", "plot_number"))
    permit_number: str | None = Field(
        default=None, validation_alias=AliasChoices("permitNumber", "permit_number", "trakheesi")
    )
    permit_status: str | None = Field(
        default=None, validation_alias=AliasChoices("permitStatus", "permit_status", "status")
    )
    owner_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ownerName",
            "owner_name",
            "landlordName",
            "landlord_name",
            "landlord",
        ),
    )
    owner_phone: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ownerPhone",
            "owner_phone",
            "landlordPhone",
            "landlord_phone",
            "landlordMobile",
            "landlord_mobile",
        ),
    )

    @field_validator("size_sqft", mode="before")
    @classmethod
    def _coerce_size(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("sqft", "").strip()
            if not cleaned:
                return None
            return float(cleaned)
        return value

    def to_listing_payload(self, *, source: str) -> ListingPayload:
        raw = self.model_dump(exclude_none=False)
        return ListingPayload(
            source=source,
            source_url=self.url,
            source_listing_id=str(self.id) if self.id is not None else None,
            unit_number=self.unit_number,
            floor=self.floor,
            building=self.building,
            community=self.community,
            developer=self.developer,
            size_sqft=self.size_sqft,
            plot_number=self.plot_number,
            permit_number=self.permit_number,
            permit_status=self.permit_status,
            owner_name=self.owner_name,
            owner_phone=self.owner_phone,
            raw_payload={"apify": raw},
        )


class ScrapeForgeListingRecord(BaseModel):
    """
    Assumed ScrapeForge response fields:
    listing_id, listing_url, unit, floor, building_name, community_name,
    developer_name, area_sqft, plot_no, permit_no, permit_status,
    owner_contact_name, owner_contact_phone, contact_name, contact_phone,
    data.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    listing_id: str | None = Field(default=None, validation_alias=AliasChoices("listing_id", "id"))
    listing_url: str | None = Field(default=None, validation_alias=AliasChoices("listing_url", "url"))
    unit_number: str | None = Field(default=None, validation_alias=AliasChoices("unit", "unit_number"))
    floor: str | None = None
    building: str | None = Field(default=None, validation_alias=AliasChoices("building_name", "building"))
    community: str | None = Field(default=None, validation_alias=AliasChoices("community_name", "community"))
    developer: str | None = Field(default=None, validation_alias=AliasChoices("developer_name", "developer"))
    size_sqft: float | None = Field(default=None, validation_alias=AliasChoices("area_sqft", "size_sqft"))
    plot_number: str | None = Field(default=None, validation_alias=AliasChoices("plot_no", "plot_number"))
    permit_number: str | None = Field(default=None, validation_alias=AliasChoices("permit_no", "permit_number"))
    permit_status: str | None = None
    owner_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("owner_contact_name", "owner_name", "landlord_name", "landlord"),
    )
    owner_phone: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "owner_contact_phone",
            "owner_phone",
            "landlord_phone",
            "landlord_mobile",
        ),
    )

    def to_listing_payload(self, *, source: str) -> ListingPayload:
        raw = self.model_dump(exclude_none=False)
        return ListingPayload(
            source=source,
            source_url=self.listing_url,
            source_listing_id=self.listing_id,
            unit_number=self.unit_number,
            floor=self.floor,
            building=self.building,
            community=self.community,
            developer=self.developer,
            size_sqft=self.size_sqft,
            plot_number=self.plot_number,
            permit_number=self.permit_number,
            permit_status=self.permit_status,
            owner_name=self.owner_name,
            owner_phone=self.owner_phone,
            raw_payload={"scrapeforge": raw},
        )


class MadmounBrokerRecord(BaseModel):
    """RERA broker card on the listing permit — not the legal property owner."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    card_holder_number: str | None = Field(default=None, validation_alias=AliasChoices("CardHolderNumber"))
    broker_name_en: str | None = Field(
        default=None, validation_alias=AliasChoices("CardHolderNameEn", "cardHolderNameEn")
    )
    broker_name_ar: str | None = Field(
        default=None, validation_alias=AliasChoices("CardHolderNameAr", "cardHolderNameAr")
    )
    broker_phone: str | None = Field(default=None, validation_alias=AliasChoices("CardHolderMobile"))
    broker_email: str | None = Field(default=None, validation_alias=AliasChoices("CardHolderEmail"))
    license_number: str | None = Field(default=None, validation_alias=AliasChoices("LicenseNumber"))
    real_estate_number: str | None = Field(default=None, validation_alias=AliasChoices("RealEstateNumber"))
    real_estate_number: str | None = Field(default=None, validation_alias=AliasChoices("RealEstateNumber"))
    permit_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PermitNumber", "permitNumber"),
    )


class MadmounIntegrationRecord(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    transaction_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PermitNumber", "transactionNumber", "TransactionNumber"),
    )
    listing_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("listingNumber", "ListingNumber", "listing_number"),
    )
    license_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LicenseNumber", "licenseNumber", "issuedLicenseNumber", "adLicense"),
    )
    owner_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ownerName",
            "owner_name",
            "landlordName",
            "titleDeedOwnerName",
            "OwnerNameEn",
            "OwnerNameAr",
        ),
    )
    owner_phone: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ownerPhone",
            "owner_phone",
            "ownerMobile",
            "OwnerMobile",
            "landlordPhone",
        ),
    )
    property_number: str | None = Field(default=None, validation_alias=AliasChoices("PropertyNumber"))
    property_size: float | None = Field(default=None, validation_alias=AliasChoices("PropertySize"))
    building_name_en: str | None = Field(default=None, validation_alias=AliasChoices("BuildingNameEn", "PropertyNameEn"))
    building_name_ar: str | None = Field(default=None, validation_alias=AliasChoices("BuildingNameAr", "PropertyNameAr"))

    def to_listing_payload(self) -> ListingPayload:
        raw = self.model_dump(exclude_none=False)
        return ListingPayload(
            source="trakheesi",
            permit_number=self.license_number or self.transaction_number,
            unit_number=self.property_number,
            building=self.building_name_en or self.building_name_ar,
            owner_name=self.owner_name,
            owner_phone=self.owner_phone,
            raw_payload={"madmoun_integration": raw},
        )


class DldPermitRecord(BaseModel):
    """
    Assumed DLD public permit lookup response fields:
    permitNumber, permitStatus, status, projectName, buildingName,
    community, developerName, propertySize, plotNumber, unitNumber,
    ownerName, ownerPhone, mobileNumber, contactNumber.
    TODO: confirm exact JSON keys against your deployed DLD endpoint response.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    permit_number: str | None = Field(
        default=None, validation_alias=AliasChoices("permitNumber", "permit_number", "licenseNumber")
    )
    permit_status: str | None = Field(
        default=None, validation_alias=AliasChoices("permitStatus", "permit_status", "status", "licenseStatus")
    )
    building: str | None = Field(default=None, validation_alias=AliasChoices("buildingName", "building"))
    community: str | None = Field(default=None, validation_alias=AliasChoices("community", "area"))
    developer: str | None = Field(default=None, validation_alias=AliasChoices("developerName", "developer"))
    size_sqft: float | None = Field(
        default=None, validation_alias=AliasChoices("propertySize", "size", "sizeSqft")
    )
    plot_number: str | None = Field(default=None, validation_alias=AliasChoices("plotNumber", "plot_number"))
    unit_number: str | None = Field(default=None, validation_alias=AliasChoices("unitNumber", "unit_number"))
    owner_name: str | None = Field(
        default=None, validation_alias=AliasChoices("ownerName", "owner_name", "contactName")
    )
    owner_phone: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ownerPhone", "owner_phone", "mobileNumber", "contactNumber", "phone"),
    )

    def to_listing_payload(self) -> ListingPayload:
        raw = self.model_dump(exclude_none=False)
        return ListingPayload(
            source="trakheesi",
            permit_number=self.permit_number,
            permit_status=self.permit_status,
            building=self.building,
            community=self.community,
            developer=self.developer,
            size_sqft=self.size_sqft,
            plot_number=self.plot_number,
            unit_number=self.unit_number,
            owner_name=self.owner_name,
            owner_phone=self.owner_phone,
            raw_payload={"dld": raw},
        )