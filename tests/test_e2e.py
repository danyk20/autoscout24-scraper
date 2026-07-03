"""End-to-end tests: real network calls against the live autoscout24.ch API.

These are marked with @pytest.mark.e2e and excluded by default (see
pyproject.toml addopts). Run them explicitly with:

    pipenv run pytest -m e2e

They intentionally target Tesla Roadster, which has a small, stable
inventory (order of ~10 listings) so the full detail-visiting pipeline and
the CLI subprocess test both run quickly without hammering the API.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

import autoscout24_scraper as scraper

pytestmark = pytest.mark.e2e

SCRIPT_PATH = str(Path(__file__).resolve().parent.parent / "autoscout24_scraper.py")


def test_resolve_make_key_real_tesla():
    session = scraper.make_session()

    key, name = scraper.resolve_make_key(session, "Tesla")

    assert key == "tesla"
    assert name == "TESLA"


def test_resolve_make_key_real_unknown_make_raises():
    session = scraper.make_session()

    with pytest.raises(ValueError):
        scraper.resolve_make_key(session, "definitely-not-a-real-car-make-xyz")


def test_resolve_model_key_real_roadster():
    session = scraper.make_session()

    key, name = scraper.resolve_model_key(session, "tesla", "Roadster")

    assert key == "roadster"
    assert name == "ROADSTER"


def test_search_listings_real_returns_at_least_one_result():
    session = scraper.make_session()

    listings = scraper.search_listings(session, "tesla", "roadster", verbose=False)

    assert len(listings) >= 1
    assert all(item["make"]["key"] == "tesla" for item in listings)
    assert all(item["model"]["key"] == "roadster" for item in listings)


def test_fetch_detail_real_listing_has_expected_fields():
    session = scraper.make_session()
    listings = scraper.search_listings(session, "tesla", "roadster", verbose=False)
    listing_id = listings[0]["id"]

    detail = scraper.fetch_detail(session, listing_id)

    assert detail["id"] == listing_id
    assert "vehicleIdentificationNumber" in detail
    assert detail["make"]["key"] == "tesla"


def test_scrape_real_full_pipeline_with_detail():
    result = scraper.scrape("Tesla", "Roadster", verbose=False)

    assert isinstance(result, scraper.ScrapeResult)
    assert result.make_key == "tesla"
    assert result.model_key == "roadster"
    assert result.total_elements >= 1
    assert len(result.rows) == result.total_elements
    assert len(result.listings) == result.total_elements

    first = result.rows[0]
    assert first["price"] != ""
    assert first["url"].startswith("https://www.autoscout24.ch/de/d/")
    # detail mode should have pulled in fields that only the detail endpoint has
    assert "vehicleIdentificationNumber" in first


def test_scrape_real_without_detail_is_faster_and_has_fewer_fields():
    result = scraper.scrape("Tesla", "Roadster", detail=False, verbose=False)

    assert result.total_elements >= 1
    # summary shape doesn't include VIN
    assert "vehicleIdentificationNumber" not in result.rows[0]


def test_scrape_real_price_filter_narrows_results():
    unfiltered = scraper.scrape("Tesla", "Roadster", detail=False, verbose=False)
    filtered = scraper.scrape("Tesla", "Roadster", detail=False, verbose=False, price_to=1)

    assert filtered.total_elements <= unfiltered.total_elements
    assert all(row["price"] == "" or float(row["price"]) <= 1 for row in filtered.rows)


def test_scrape_result_round_trips_through_real_files(tmp_path):
    result = scraper.scrape("Tesla", "Roadster", detail=False, verbose=False)
    csv_path = tmp_path / "roadster.csv"
    json_path = tmp_path / "roadster.json"

    result.to_csv(str(csv_path))
    result.to_json(str(json_path))

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == result.total_elements

    with open(json_path, encoding="utf-8") as f:
        listings = json.load(f)
    assert len(listings) == result.total_elements
    assert listings[0]["make"]["key"] == "tesla"


def test_cli_subprocess_end_to_end_writes_real_files(tmp_path):
    out_base = tmp_path / "roadster_cli"

    proc = subprocess.run(
        [
            sys.executable,
            SCRIPT_PATH,
            "--make",
            "Tesla",
            "--model",
            "Roadster",
            "--no-detail",  # keep the e2e suite fast
            "--out",
            str(out_base),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "Done." in proc.stdout

    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")
    assert csv_path.exists()
    assert json_path.exists()

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1


def test_cli_subprocess_unknown_make_exits_with_error(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            SCRIPT_PATH,
            "--make",
            "not-a-real-make-xyz",
            "--model",
            "whatever",
            "--out",
            str(tmp_path / "should_not_exist"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 1
    assert "Error:" in proc.stderr
    assert not (tmp_path / "should_not_exist.csv").exists()
