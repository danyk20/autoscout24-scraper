"""Unit tests for search_listings(), fetch_detail() and visit_all_listings()."""

import json

import pytest
import responses

import autoscout24_scraper as scraper

SEARCH_URL = f"{scraper.API_BASE}/listings/search"


def search_page(content, total_pages, total_elements, number):
    return {
        "content": content,
        "empty": len(content) == 0,
        "first": number == 0,
        "last": number == total_pages - 1,
        "number": number,
        "numberOfElements": len(content),
        "size": scraper.PAGE_SIZE,
        "totalElements": total_elements,
        "totalPages": total_pages,
    }


@pytest.fixture
def sleep_spy(monkeypatch):
    calls = []
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: calls.append(seconds))
    return calls


@responses.activate
def test_search_listings_single_page(summary_listing_factory, sleep_spy):
    listings = [summary_listing_factory(1), summary_listing_factory(2)]
    responses.add(responses.POST, SEARCH_URL, json=search_page(listings, 1, 2, 0), status=200)
    session = scraper.make_session()

    result = scraper.search_listings(session, "tesla", "model-s", verbose=False)

    assert [item["id"] for item in result] == [1, 2]
    assert len(responses.calls) == 1
    # no inter-page delay needed for a single page
    assert sleep_spy == []


@responses.activate
def test_search_listings_paginates_and_dedupes(summary_listing_factory, sleep_spy):
    page0 = [summary_listing_factory(i) for i in range(1, 21)]
    # id 20 reappears on page 1 (simulates the boosted-listing reshuffle) and
    # should not be double-counted.
    page1 = [summary_listing_factory(20)] + [summary_listing_factory(i) for i in range(21, 40)]
    responses.add(responses.POST, SEARCH_URL, json=search_page(page0, 2, 39, 0), status=200)
    responses.add(responses.POST, SEARCH_URL, json=search_page(page1, 2, 39, 1), status=200)
    session = scraper.make_session()

    result = scraper.search_listings(session, "tesla", "model-s", verbose=False, delay=0.01)

    ids = [item["id"] for item in result]
    assert len(ids) == len(set(ids)) == 39
    assert len(responses.calls) == 2
    # one delay between the two pages, none after the last
    assert sleep_spy == [0.01]


@responses.activate
def test_search_listings_sends_stable_sort_and_pagination(summary_listing_factory):
    responses.add(responses.POST, SEARCH_URL, json=search_page([], 1, 0, 0), status=200)
    session = scraper.make_session()

    scraper.search_listings(session, "tesla", "model-s", verbose=False)

    body = json.loads(responses.calls[0].request.body)
    assert body["sort"] == [{"type": "PRICE", "order": "ASC"}]
    assert body["pagination"] == {"page": 0, "size": scraper.PAGE_SIZE}
    assert body["query"]["makeModelVersions"] == [{"makeKey": "tesla", "modelKey": "model-s"}]
    assert body["query"]["vehicleCategories"] == ["car"]


@responses.activate
def test_search_listings_only_includes_filters_that_are_set(summary_listing_factory):
    responses.add(responses.POST, SEARCH_URL, json=search_page([], 1, 0, 0), status=200)
    session = scraper.make_session()

    scraper.search_listings(session, "tesla", "model-s", verbose=False, price_to=30000, year_from=2018)

    body = json.loads(responses.calls[0].request.body)
    assert body["query"]["priceTo"] == 30000
    assert body["query"]["firstRegistrationYearFrom"] == 2018
    assert "priceFrom" not in body["query"]
    assert "mileageFrom" not in body["query"]
    assert "mileageTo" not in body["query"]
    assert "firstRegistrationYearTo" not in body["query"]


@responses.activate
def test_search_listings_includes_all_six_filters_when_set(summary_listing_factory):
    responses.add(responses.POST, SEARCH_URL, json=search_page([], 1, 0, 0), status=200)
    session = scraper.make_session()

    scraper.search_listings(
        session,
        "tesla",
        "model-s",
        verbose=False,
        price_from=1000,
        price_to=2000,
        mileage_from=10,
        mileage_to=20,
        year_from=2015,
        year_to=2020,
    )

    body = json.loads(responses.calls[0].request.body)
    assert body["query"]["priceFrom"] == 1000
    assert body["query"]["priceTo"] == 2000
    assert body["query"]["mileageFrom"] == 10
    assert body["query"]["mileageTo"] == 20
    assert body["query"]["firstRegistrationYearFrom"] == 2015
    assert body["query"]["firstRegistrationYearTo"] == 2020


@responses.activate
def test_search_listings_verbose_prints_progress(summary_listing_factory, capsys):
    responses.add(responses.POST, SEARCH_URL, json=search_page([summary_listing_factory(1)], 1, 1, 0), status=200)
    session = scraper.make_session()

    scraper.search_listings(session, "tesla", "model-s", verbose=True)

    out = capsys.readouterr().out
    assert "page 1/1" in out
    assert "API reports 1 total matches" in out


@responses.activate
def test_search_listings_silent_when_not_verbose(summary_listing_factory, capsys):
    responses.add(responses.POST, SEARCH_URL, json=search_page([summary_listing_factory(1)], 1, 1, 0), status=200)
    session = scraper.make_session()

    scraper.search_listings(session, "tesla", "model-s", verbose=False)

    assert capsys.readouterr().out == ""


@responses.activate
def test_search_listings_embeds_full_ad_url_on_every_item(summary_listing_factory):
    listings = [summary_listing_factory(1), summary_listing_factory(2)]
    responses.add(responses.POST, SEARCH_URL, json=search_page(listings, 1, 2, 0), status=200)
    session = scraper.make_session()

    result = scraper.search_listings(session, "tesla", "model-s", verbose=False)

    assert result[0]["url"] == "https://www.autoscout24.ch/de/d/1"
    assert result[1]["url"] == "https://www.autoscout24.ch/de/d/2"


@responses.activate
def test_search_listings_uses_custom_domain_for_api_and_url(summary_listing_factory):
    listing = summary_listing_factory(1)
    de_search_url = f"{scraper.api_base('de')}/listings/search"
    responses.add(responses.POST, de_search_url, json=search_page([listing], 1, 1, 0), status=200)
    session = scraper.make_session()

    result = scraper.search_listings(session, "tesla", "model-s", verbose=False, domain="de")

    assert result[0]["url"] == "https://www.autoscout24.de/de/d/1"
    assert responses.calls[0].request.url.startswith(de_search_url)


DETAIL_URL_TEMPLATE = f"{scraper.API_BASE}/listings/{{id}}"


@responses.activate
def test_fetch_detail(detail_listing_factory):
    detail = detail_listing_factory(42)
    responses.add(responses.GET, DETAIL_URL_TEMPLATE.format(id=42), json=detail, status=200)
    session = scraper.make_session()

    result = scraper.fetch_detail(session, 42)

    assert result == detail


@responses.activate
def test_fetch_detail_uses_custom_domain(detail_listing_factory):
    detail = detail_listing_factory(42)
    de_detail_url = f"{scraper.api_base('de')}/listings/42"
    responses.add(responses.GET, de_detail_url, json=detail, status=200)
    session = scraper.make_session()

    result = scraper.fetch_detail(session, 42, domain="de")

    assert result == detail


@responses.activate
def test_visit_all_listings_merges_seller_and_returns_detail_shape(
    summary_listing_factory,
    detail_listing_factory,
    sleep_spy,
):
    summary_items = [summary_listing_factory(1), summary_listing_factory(2)]
    detail_1 = detail_listing_factory(1)
    detail_2 = detail_listing_factory(2)
    responses.add(responses.GET, DETAIL_URL_TEMPLATE.format(id=1), json=detail_1, status=200)
    responses.add(responses.GET, DETAIL_URL_TEMPLATE.format(id=2), json=detail_2, status=200)
    session = scraper.make_session()

    result = scraper.visit_all_listings(session, summary_items, delay=0.05, verbose=False)

    assert len(result) == 2
    # detail records don't have a "seller" key of their own; it should have
    # been backfilled from the search summary.
    assert result[0]["seller"] == summary_items[0]["seller"]
    assert result[1]["seller"] == summary_items[1]["seller"]
    assert result[0]["vehicleIdentificationNumber"] == detail_1["vehicleIdentificationNumber"]
    # one delay between the two visits, none after the last
    assert sleep_spy == [0.05]


@responses.activate
def test_visit_all_listings_embeds_full_ad_url(summary_listing_factory, detail_listing_factory):
    summary_items = [summary_listing_factory(7)]
    responses.add(responses.GET, DETAIL_URL_TEMPLATE.format(id=7), json=detail_listing_factory(7), status=200)
    session = scraper.make_session()

    result = scraper.visit_all_listings(session, summary_items, delay=0, verbose=False)

    assert result[0]["url"] == "https://www.autoscout24.ch/de/d/7"


@responses.activate
def test_visit_all_listings_uses_custom_domain_for_api_and_url(summary_listing_factory, detail_listing_factory):
    summary_items = [summary_listing_factory(7)]
    de_detail_url = f"{scraper.api_base('de')}/listings/7"
    responses.add(responses.GET, de_detail_url, json=detail_listing_factory(7), status=200)
    session = scraper.make_session()

    result = scraper.visit_all_listings(session, summary_items, delay=0, verbose=False, domain="de")

    assert result[0]["url"] == "https://www.autoscout24.de/de/d/7"


@responses.activate
def test_visit_all_listings_prints_progress_every_ten_and_at_end(summary_listing_factory, capsys):
    items = [summary_listing_factory(i) for i in range(1, 12)]
    for item in items:
        responses.add(responses.GET, DETAIL_URL_TEMPLATE.format(id=item["id"]), json=item, status=200)
    session = scraper.make_session()

    scraper.visit_all_listings(session, items, delay=0, verbose=True)

    out = capsys.readouterr().out
    assert "visited 10/11" in out
    assert "visited 11/11" in out


def test_listing_url_format():
    assert scraper.listing_url(12345) == "https://www.autoscout24.ch/de/d/12345"


def test_listing_url_with_custom_domain():
    assert scraper.listing_url(12345, domain="de") == "https://www.autoscout24.de/de/d/12345"


def test_api_base_default_is_ch():
    assert scraper.api_base() == "https://api.autoscout24.ch/v1"
    assert scraper.api_base() == scraper.API_BASE


def test_api_base_with_custom_domain():
    assert scraper.api_base("fr") == "https://api.autoscout24.fr/v1"
