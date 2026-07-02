"""Unit tests for save_csv(), save_json() and ScrapeResult."""
import csv
import json
import os

import autoscout24_scraper as scraper


def test_save_csv_writes_header_and_rows(tmp_path):
    rows = [
        {"id": 1, "price": 100},
        {"id": 2, "price": 200},
    ]
    path = tmp_path / "out.csv"

    scraper.save_csv(rows, str(path))

    with open(path, newline="", encoding="utf-8") as f:
        read_rows = list(csv.DictReader(f))
    assert [r["id"] for r in read_rows] == ["1", "2"]
    assert [r["price"] for r in read_rows] == ["100", "200"]


def test_save_csv_union_of_keys_fills_missing_with_empty_string(tmp_path):
    rows = [
        {"id": 1, "price": 100},
        {"id": 2, "extra_field": "only on this row"},
    ]
    path = tmp_path / "out.csv"

    scraper.save_csv(rows, str(path))

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        read_rows = list(reader)

    assert set(fieldnames) == {"id", "price", "extra_field"}
    assert read_rows[0]["extra_field"] == ""
    assert read_rows[1]["price"] == ""
    assert read_rows[1]["extra_field"] == "only on this row"


def test_save_csv_orders_priority_fields_first(tmp_path):
    rows = [{"zzz": "z", "id": 1, "price": 100, "make": "TESLA"}]
    path = tmp_path / "out.csv"

    scraper.save_csv(rows, str(path))

    with open(path, newline="", encoding="utf-8") as f:
        fieldnames = csv.DictReader(f).fieldnames

    assert fieldnames.index("id") < fieldnames.index("zzz")
    assert fieldnames.index("make") < fieldnames.index("zzz")
    assert fieldnames.index("price") < fieldnames.index("zzz")


def test_save_csv_with_no_rows_warns_and_writes_nothing(tmp_path, capsys):
    path = tmp_path / "out.csv"

    scraper.save_csv([], str(path))

    assert not path.exists()
    assert "no rows to write" in capsys.readouterr().out


def test_save_csv_preserves_unicode(tmp_path):
    rows = [{"id": 1, "teaser": "Klimaanlage, gepflegtes Fahrzeug, 100'000 Fr."}]
    path = tmp_path / "out.csv"

    scraper.save_csv(rows, str(path))

    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "Klimaanlage" in content


def test_save_json_round_trips_data(tmp_path):
    data = [{"id": 1, "nested": {"a": 1}}, {"id": 2, "nested": None}]
    path = tmp_path / "out.json"

    scraper.save_json(data, str(path))

    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_save_json_preserves_unicode_without_escaping(tmp_path):
    data = [{"teaser": "Wagen mit Vollausstattung, überdurchschnittlich gepflegt"}]
    path = tmp_path / "out.json"

    scraper.save_json(data, str(path))

    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "überdurchschnittlich" in content


# --- ScrapeResult ----------------------------------------------------------

def _make_result(rows, listings):
    return scraper.ScrapeResult(
        make_key="tesla", make_name="TESLA",
        model_key="model-s", model_name="MODEL S",
        category="car", total_elements=len(listings),
        listings=listings, rows=rows,
    )


def test_scrape_result_to_csv_writes_rows(tmp_path):
    result = _make_result(rows=[{"id": 1, "price": 100}], listings=[{"id": 1}])
    path = tmp_path / "r.csv"

    result.to_csv(str(path))

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["id"] == "1"


def test_scrape_result_to_json_writes_raw_listings_not_flattened_rows(tmp_path):
    listings = [{"id": 1, "nested": {"a": 1}}]
    result = _make_result(rows=[{"id": 1, "nested_a": 1}], listings=listings)
    path = tmp_path / "r.json"

    result.to_json(str(path))

    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == listings


def test_scrape_result_defaults_to_empty_lists_when_not_provided():
    result = scraper.ScrapeResult(
        make_key="tesla", make_name="TESLA",
        model_key="model-s", model_name="MODEL S",
        category="car", total_elements=0,
    )
    assert result.listings == []
    assert result.rows == []


def test_scrape_result_defaults_to_ch_domain_when_not_provided():
    result = scraper.ScrapeResult(
        make_key="tesla", make_name="TESLA",
        model_key="model-s", model_name="MODEL S",
        category="car", total_elements=0,
    )
    assert result.domain == "ch"


def test_scrape_result_accepts_custom_domain():
    result = scraper.ScrapeResult(
        make_key="tesla", make_name="TESLA",
        model_key="model-s", model_name="MODEL S",
        category="car", total_elements=0, domain="de",
    )
    assert result.domain == "de"
