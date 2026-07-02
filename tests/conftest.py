"""Shared fixtures for the unit test suite.

The sample payloads below mirror the real shapes returned by
api.autoscout24.ch (captured by hand while reverse-engineering the API) so
that mocked HTTP responses exercise the same code paths real ones would.
"""
import pytest

import autoscout24_scraper as scraper


@pytest.fixture
def makes_payload():
    return [
        {"id": 209, "key": "ac", "name": "AC"},
        {"id": 391, "key": "tesla", "name": "TESLA"},
        {"id": 100, "key": "bmw", "name": "BMW"},
        # name contains a space where the key uses a dash, so an exact-name
        # query only matches on the second lookup pass, not the key pass.
        {"id": 500, "key": "aston-martin", "name": "ASTON MARTIN"},
    ]


@pytest.fixture
def tesla_models_payload():
    return [
        {"id": 7240, "key": "cybertruck", "name": "CYBERTRUCK", "group": None},
        {"id": 2864, "key": "model-3", "name": "MODEL 3", "group": None},
        {"id": 1919, "key": "model-s", "name": "MODEL S", "group": None},
        {"id": 2305, "key": "model-x", "name": "MODEL X", "group": None},
        {"id": 3281, "key": "model-y", "name": "MODEL Y", "group": None},
        {"id": 1094, "key": "roadster", "name": "ROADSTER", "group": None},
    ]


def make_summary_listing(listing_id, price=27900.0, mileage=150000, top_list=False):
    """A search-result-shaped listing (the summary shape)."""
    return {
        "conditionType": "used",
        "consumption": {"combined": None},
        "createdDate": "2025-11-10T08:10:06.118Z",
        "features": [{"feature": "top-list"}] if top_list else [],
        "financing": {
            "providerName": "FinanceScout24",
            "url": f"https://kredit.financescout24.ch/de/inquiry/amount?vehicleId={listing_id}",
        },
        "firstRegistrationDate": "2020-12-01",
        "firstRegistrationYear": 2020,
        "fuelType": "electric",
        "hadAccident": False,
        "hasAdditionalSetOfTires": True,
        "hasNewTires": None,
        "horsePower": 585,
        "id": listing_id,
        "images": [{"key": f"listing/{listing_id}/1.jpeg"}, {"key": f"listing/{listing_id}/2.jpeg"}],
        "inspected": True,
        "insurance": {
            "providerName": "FinanceScout24",
            "url": f"https://www.financescout24.ch/de/autoversicherung-finden?vehicleId={listing_id}",
        },
        "kiloWatts": 430,
        "lastModifiedDate": "2026-04-15T13:44:34.442Z",
        "leasing": None,
        "make": {"id": 391, "name": "TESLA", "key": "tesla"},
        "mileage": mileage,
        "model": {"id": 1919, "name": "MODEL S", "key": "model-s"},
        "previousPrice": None,
        "price": price,
        "qualiLogoId": None,
        "qualiLogo": None,
        "range": 652,
        "seller": {
            "city": "Yverdon-les-Bains",
            "features": [],
            "id": 3001640,
            "logoKey": None,
            "name": "EGEN",
            "type": "private",
            "zipCode": "1400",
        },
        "teaser": "Sample teaser text",
        "transmissionType": "automatic",
        "transmissionTypeGroup": None,
        "vehicleCategory": "car",
        "versionFullName": "Raven Long Range FSD",
        "warranty": {"type": "none"},
    }


def make_detail_listing(listing_id, price=27900.0, mileage=150000):
    """A detail-endpoint-shaped listing: many more scalar fields, seller
    collapses down to a bare sellerId (no name/city/zip/type)."""
    return {
        "availableForExchange": None,
        "availableForLeasing": None,
        "batteryCapacity": 100.0,
        "bodyColor": "red",
        "bodyType": "saloon",
        "boot": {"height": None, "length": None, "volume": None, "width": None},
        "conditionType": "used",
        "consumption": {"combined": None, "extraUrban": None, "urban": None},
        "createdDate": "2025-11-10T08:10:06.118Z",
        "description": "A great car with a long description.",
        "documents": [],
        "doors": 5,
        "driveType": "all",
        "features": [{"feature": "top-list"}],
        "financing": {
            "providerName": "FinanceScout24",
            "url": f"https://kredit.financescout24.ch/de/inquiry/amount?vehicleId={listing_id}",
        },
        "firstRegistrationDate": "2020-12-01",
        "firstRegistrationYear": 2020,
        "fuelType": "electric",
        "hadAccident": False,
        "horsePower": 585,
        "id": listing_id,
        "images": [{"key": f"listing/{listing_id}/1.jpeg"}, {"key": f"listing/{listing_id}/2.jpeg"}],
        "inspected": True,
        "insurance": {
            "providerName": "FinanceScout24",
            "url": f"https://www.financescout24.ch/de/autoversicherung-finden?vehicleId={listing_id}",
        },
        "kiloWatts": 430,
        "lastModifiedDate": "2026-04-15T13:44:34.442Z",
        "make": {"id": 391, "name": "TESLA", "key": "tesla"},
        "mileage": mileage,
        "model": {"id": 1919, "name": "MODEL S", "key": "model-s"},
        "price": price,
        "previousPrice": None,
        "range": 652,
        "sellerId": 3001640,
        "teaser": "Sample teaser text",
        "transmissionType": "automatic",
        "vehicleCategory": "car",
        "vehicleIdentificationNumber": "5YJSA1E2XKF000001",
        "versionFullName": "Raven Long Range FSD",
        "warranty": {"type": "none"},
    }


@pytest.fixture
def summary_listing_factory():
    return make_summary_listing


@pytest.fixture
def detail_listing_factory():
    return make_detail_listing


@pytest.fixture
def no_sleep(monkeypatch):
    """Make time.sleep a no-op so tests exercising delay loops run instantly."""
    monkeypatch.setattr(scraper.time, "sleep", lambda *_args, **_kwargs: None)
