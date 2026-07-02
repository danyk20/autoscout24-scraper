"""Unit tests for resolve_make_key() and resolve_model_key()."""
import pytest
import responses

import autoscout24_scraper as scraper

MAKES_URL = f"{scraper.API_BASE}/makes"


def models_url(make_key, domain=scraper.DEFAULT_DOMAIN):
    return f"{scraper.api_base(domain)}/makes/key/{make_key}/models"


@responses.activate
def test_resolve_make_key_by_exact_key(makes_payload):
    responses.add(responses.GET, MAKES_URL, json=makes_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_make_key(session, "tesla")

    assert (key, name) == ("tesla", "TESLA")


@responses.activate
def test_resolve_make_key_by_exact_name_case_insensitive(makes_payload):
    responses.add(responses.GET, MAKES_URL, json=makes_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_make_key(session, "Tesla")

    assert (key, name) == ("tesla", "TESLA")


@responses.activate
def test_resolve_make_key_by_exact_name_when_name_and_key_differ(makes_payload):
    # "aston-martin" (key) vs "ASTON MARTIN" (name): an exact-key check on
    # the lowercased query can't match here, so this exercises the
    # dedicated exact-name lookup pass.
    responses.add(responses.GET, MAKES_URL, json=makes_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_make_key(session, "Aston Martin")

    assert (key, name) == ("aston-martin", "ASTON MARTIN")


@responses.activate
def test_resolve_make_key_by_partial_substring_match(makes_payload):
    responses.add(responses.GET, MAKES_URL, json=makes_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_make_key(session, "esl")

    assert (key, name) == ("tesla", "TESLA")


@responses.activate
def test_resolve_make_key_not_found_raises(makes_payload):
    responses.add(responses.GET, MAKES_URL, json=makes_payload, status=200)
    session = scraper.make_session()

    with pytest.raises(ValueError, match="Could not find a make matching"):
        scraper.resolve_make_key(session, "totally-not-a-make")


@responses.activate
def test_resolve_make_key_passes_vehicle_category_param(makes_payload):
    responses.add(responses.GET, MAKES_URL, json=makes_payload, status=200)
    session = scraper.make_session()

    scraper.resolve_make_key(session, "tesla", vehicle_category="motorcycle")

    assert responses.calls[0].request.params["vehicleCategory"] == "motorcycle"


@responses.activate
def test_resolve_make_key_uses_custom_domain(makes_payload):
    de_makes_url = f"{scraper.api_base('de')}/makes"
    responses.add(responses.GET, de_makes_url, json=makes_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_make_key(session, "tesla", domain="de")

    assert (key, name) == ("tesla", "TESLA")
    assert responses.calls[0].request.url.startswith(de_makes_url)


@responses.activate
def test_resolve_model_key_by_exact_key(tesla_models_payload):
    responses.add(responses.GET, models_url("tesla"), json=tesla_models_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_model_key(session, "tesla", "model-s")

    assert (key, name) == ("model-s", "MODEL S")


@responses.activate
def test_resolve_model_key_by_exact_name_case_insensitive(tesla_models_payload):
    responses.add(responses.GET, models_url("tesla"), json=tesla_models_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_model_key(session, "tesla", "Model S")

    assert (key, name) == ("model-s", "MODEL S")


@responses.activate
def test_resolve_model_key_by_partial_substring_match(tesla_models_payload):
    responses.add(responses.GET, models_url("tesla"), json=tesla_models_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_model_key(session, "tesla", "road")

    assert (key, name) == ("roadster", "ROADSTER")


@responses.activate
def test_resolve_model_key_not_found_lists_available_models(tesla_models_payload):
    responses.add(responses.GET, models_url("tesla"), json=tesla_models_payload, status=200)
    session = scraper.make_session()

    with pytest.raises(ValueError) as excinfo:
        scraper.resolve_model_key(session, "tesla", "not-a-model")

    message = str(excinfo.value)
    assert "not-a-model" in message
    assert "MODEL S" in message
    assert "ROADSTER" in message


@responses.activate
def test_resolve_model_key_uses_custom_domain(tesla_models_payload):
    de_models_url = models_url("tesla", domain="de")
    responses.add(responses.GET, de_models_url, json=tesla_models_payload, status=200)
    session = scraper.make_session()

    key, name = scraper.resolve_model_key(session, "tesla", "model-s", domain="de")

    assert (key, name) == ("model-s", "MODEL S")
    assert responses.calls[0].request.url.startswith(de_models_url)
