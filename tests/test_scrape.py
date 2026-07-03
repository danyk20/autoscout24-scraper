"""Unit tests for the scrape() library entry point (orchestration logic).

These monkeypatch the building-block functions (resolve_make_key,
resolve_model_key, search_listings, visit_all_listings) so we can test the
orchestration in isolation from HTTP. End-to-end tests that hit the real
API live in test_e2e.py.
"""

import pytest

import autoscout24_scraper as scraper


@pytest.fixture
def patched_pipeline(monkeypatch, summary_listing_factory, detail_listing_factory):
    """Patch out every network-touching function scrape() calls, and record
    how they were called."""
    calls = {}

    def fake_resolve_make_key(session, make_query, vehicle_category="car", domain=scraper.DEFAULT_DOMAIN):
        calls["resolve_make_key"] = (session, make_query, vehicle_category, domain)
        return "tesla", "TESLA"

    def fake_resolve_model_key(session, make_key, model_query, vehicle_category="car", domain=scraper.DEFAULT_DOMAIN):
        calls["resolve_model_key"] = (session, make_key, model_query, vehicle_category, domain)
        return "model-s", "MODEL S"

    def fake_search_listings(
        session,
        make_key,
        model_key,
        vehicle_category="car",
        delay=0.4,
        verbose=True,
        domain=scraper.DEFAULT_DOMAIN,
        **filters,
    ):
        calls["search_listings"] = dict(
            make_key=make_key,
            model_key=model_key,
            vehicle_category=vehicle_category,
            delay=delay,
            verbose=verbose,
            domain=domain,
            filters=filters,
        )
        return [summary_listing_factory(1, price=200), summary_listing_factory(2, price=100)]

    def fake_visit_all_listings(session, listings, delay=0.4, verbose=True, domain=scraper.DEFAULT_DOMAIN):
        calls["visit_all_listings"] = dict(listings=listings, delay=delay, verbose=verbose, domain=domain)
        return [detail_listing_factory(item["id"], price=item["price"]) for item in listings]

    monkeypatch.setattr(scraper, "resolve_make_key", fake_resolve_make_key)
    monkeypatch.setattr(scraper, "resolve_model_key", fake_resolve_model_key)
    monkeypatch.setattr(scraper, "search_listings", fake_search_listings)
    monkeypatch.setattr(scraper, "visit_all_listings", fake_visit_all_listings)

    return calls


def test_scrape_happy_path_returns_scrape_result(patched_pipeline):
    result = scraper.scrape("Tesla", "Model S", verbose=False)

    assert isinstance(result, scraper.ScrapeResult)
    assert result.make_key == "tesla"
    assert result.make_name == "TESLA"
    assert result.model_key == "model-s"
    assert result.model_name == "MODEL S"
    assert result.category == "car"
    assert result.total_elements == 2
    assert len(result.rows) == 2
    assert len(result.listings) == 2


def test_scrape_calls_resolve_functions_with_given_make_model(patched_pipeline):
    scraper.scrape("Tesla", "Model S", verbose=False)

    assert patched_pipeline["resolve_make_key"][1] == "Tesla"
    assert patched_pipeline["resolve_model_key"][2] == "Model S"
    assert patched_pipeline["resolve_model_key"][1] == "tesla"  # uses resolved make key


def test_scrape_passes_category_through(patched_pipeline):
    scraper.scrape("Tesla", "Model S", category="motorcycle", verbose=False)

    assert patched_pipeline["resolve_make_key"][2] == "motorcycle"
    assert patched_pipeline["search_listings"]["vehicle_category"] == "motorcycle"


def test_scrape_defaults_to_ch_domain(patched_pipeline):
    result = scraper.scrape("Tesla", "Model S", verbose=False)

    assert result.domain == "ch"
    assert patched_pipeline["resolve_make_key"][3] == "ch"
    assert patched_pipeline["resolve_model_key"][4] == "ch"
    assert patched_pipeline["search_listings"]["domain"] == "ch"
    assert patched_pipeline["visit_all_listings"]["domain"] == "ch"


def test_scrape_passes_custom_domain_through(patched_pipeline):
    result = scraper.scrape("Tesla", "Model S", domain="de", verbose=False)

    assert result.domain == "de"
    assert patched_pipeline["resolve_make_key"][3] == "de"
    assert patched_pipeline["resolve_model_key"][4] == "de"
    assert patched_pipeline["search_listings"]["domain"] == "de"
    assert patched_pipeline["visit_all_listings"]["domain"] == "de"


def test_scrape_verbose_mentions_domain(patched_pipeline, caplog):
    with caplog.at_level("INFO", logger="autoscout24_scraper"):
        scraper.scrape("Tesla", "Model S", domain="de", verbose=True)

    assert "autoscout24.de" in caplog.text


def test_scrape_passes_all_filters_through(patched_pipeline):
    scraper.scrape(
        "Tesla",
        "Model S",
        verbose=False,
        price_from=1,
        price_to=2,
        mileage_from=3,
        mileage_to=4,
        year_from=5,
        year_to=6,
    )

    filters = patched_pipeline["search_listings"]["filters"]
    assert filters == {
        "price_from": 1,
        "price_to": 2,
        "mileage_from": 3,
        "mileage_to": 4,
        "year_from": 5,
        "year_to": 6,
    }


def test_scrape_detail_true_by_default_visits_every_listing(patched_pipeline):
    scraper.scrape("Tesla", "Model S", verbose=False)

    assert "visit_all_listings" in patched_pipeline
    assert len(patched_pipeline["visit_all_listings"]["listings"]) == 2


def test_scrape_detail_false_skips_visiting(patched_pipeline):
    result = scraper.scrape("Tesla", "Model S", detail=False, verbose=False)

    assert "visit_all_listings" not in patched_pipeline
    # rows/listings should come straight from the (summary-shaped) search results
    assert result.listings[0]["price"] == 200


def test_scrape_rows_sorted_ascending_by_price(patched_pipeline):
    result = scraper.scrape("Tesla", "Model S", verbose=False)

    prices = [row["price"] for row in result.rows]
    assert prices == sorted(prices)


def test_scrape_rows_with_missing_price_sort_last(monkeypatch, summary_listing_factory):
    listing_no_price = summary_listing_factory(3, price=100)
    listing_no_price["price"] = None
    listing_with_price = summary_listing_factory(4, price=50)

    monkeypatch.setattr(scraper, "resolve_make_key", lambda *a, **k: ("tesla", "TESLA"))
    monkeypatch.setattr(scraper, "resolve_model_key", lambda *a, **k: ("model-s", "MODEL S"))
    monkeypatch.setattr(
        scraper,
        "search_listings",
        lambda *a, **k: [listing_no_price, listing_with_price],
    )

    result = scraper.scrape("Tesla", "Model S", detail=False, verbose=False)

    assert result.rows[-1]["price"] == ""  # missing price sorts to the end
    assert result.rows[0]["price"] == 50


def test_scrape_verbose_false_prints_nothing(patched_pipeline, capsys):
    scraper.scrape("Tesla", "Model S", verbose=False)

    assert capsys.readouterr().out == ""


def test_scrape_verbose_true_prints_progress(patched_pipeline, caplog):
    with caplog.at_level("INFO", logger="autoscout24_scraper"):
        scraper.scrape("Tesla", "Model S", verbose=True)

    out = caplog.text
    assert "Resolving make 'Tesla'" in out
    assert "Resolving model 'Model S'" in out
    assert "Fetching listings for TESLA MODEL S" in out


def test_scrape_verbose_notes_active_filters(patched_pipeline, caplog):
    with caplog.at_level("INFO", logger="autoscout24_scraper"):
        scraper.scrape("Tesla", "Model S", verbose=True, price_to=30000, year_from=2018)

    out = caplog.text
    assert "price 0-30000 CHF" in out
    assert "year 2018-" in out


def test_scrape_verbose_notes_mileage_filter(patched_pipeline, caplog):
    with caplog.at_level("INFO", logger="autoscout24_scraper"):
        scraper.scrape("Tesla", "Model S", verbose=True, mileage_to=60000)

    out = caplog.text
    assert "mileage 0-60000 km" in out


def test_scrape_reuses_provided_session(patched_pipeline):
    sentinel_session = object()

    scraper.scrape("Tesla", "Model S", verbose=False, session=sentinel_session)

    assert patched_pipeline["resolve_make_key"][0] is sentinel_session


@pytest.mark.parametrize(
    "kwargs",
    [
        {"price_from": 100, "price_to": 50},
        {"mileage_from": 100, "mileage_to": 50},
        {"year_from": 2020, "year_to": 2010},
    ],
)
def test_scrape_raises_on_inverted_ranges_before_any_network_call(patched_pipeline, kwargs):
    with pytest.raises(ValueError, match="cannot be greater than"):
        scraper.scrape("Tesla", "Model S", verbose=False, **kwargs)

    # validation must happen before any resolving/searching occurs
    assert patched_pipeline == {}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"price_from": 50, "price_to": 50},
        {"mileage_from": 50, "mileage_to": 50},
        {"year_from": 2020, "year_to": 2020},
    ],
)
def test_scrape_allows_equal_from_and_to(patched_pipeline, kwargs):
    # equal bounds are a valid (if narrow) range, not an error
    scraper.scrape("Tesla", "Model S", verbose=False, **kwargs)
