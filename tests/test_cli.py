"""Unit tests for main() (CLI argument handling) and run_cli() (exit codes).

scrape() itself is monkeypatched here so these tests never touch the
network; they only verify that CLI flags are translated into the right
scrape() call and that files get written to the right place.
"""

import csv
import json

import pytest
import requests

import autoscout24_scraper as scraper


@pytest.fixture
def fake_scrape(monkeypatch):
    calls = {}

    def _fake_scrape(make, model, **kwargs):
        calls["make"] = make
        calls["model"] = model
        calls["kwargs"] = kwargs
        return scraper.ScrapeResult(
            make_key="tesla",
            make_name="TESLA",
            model_key="model-s",
            model_name="MODEL S",
            category=kwargs.get("category", "car"),
            total_elements=1,
            listings=[{"id": 1, "price": 100}],
            rows=[{"id": 1, "price": 100, "url": "https://www.autoscout24.ch/de/d/1"}],
        )

    monkeypatch.setattr(scraper, "scrape", _fake_scrape)
    return calls


def test_main_translates_required_flags(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = scraper.main(["--make", "Tesla", "--model", "Model S"])

    assert exit_code == 0
    assert fake_scrape["make"] == "Tesla"
    assert fake_scrape["model"] == "Model S"
    assert fake_scrape["kwargs"]["category"] == "car"
    assert fake_scrape["kwargs"]["detail"] is True  # detail is on unless --no-detail
    assert fake_scrape["kwargs"]["domain"] == "ch"  # default domain unless --domain is given


def test_main_passes_custom_domain(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Model S", "--domain", "de"])

    assert fake_scrape["kwargs"]["domain"] == "de"


def test_main_no_detail_flag_disables_detail(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Model S", "--no-detail"])

    assert fake_scrape["kwargs"]["detail"] is False


def test_main_passes_range_filters(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(
        [
            "--make",
            "Tesla",
            "--model",
            "Model S",
            "--price-from",
            "1000",
            "--price-to",
            "2000",
            "--mileage-from",
            "10",
            "--mileage-to",
            "20",
            "--year-from",
            "2015",
            "--year-to",
            "2020",
        ]
    )

    kwargs = fake_scrape["kwargs"]
    assert kwargs["price_from"] == 1000
    assert kwargs["price_to"] == 2000
    assert kwargs["mileage_from"] == 10
    assert kwargs["mileage_to"] == 20
    assert kwargs["year_from"] == 2015
    assert kwargs["year_to"] == 2020


def test_main_passes_custom_delay(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Model S", "--delay", "1.5"])

    assert fake_scrape["kwargs"]["delay"] == 1.5


def test_main_passes_category(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Roadster", "--category", "motorcycle"])

    assert fake_scrape["kwargs"]["category"] == "motorcycle"


def test_main_writes_csv_and_json_with_default_filename(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Model S"])

    assert (tmp_path / "tesla_model-s.csv").exists()
    assert (tmp_path / "tesla_model-s.json").exists()

    with open(tmp_path / "tesla_model-s.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["id"] == "1"

    with open(tmp_path / "tesla_model-s.json", encoding="utf-8") as f:
        listings = json.load(f)
    assert listings == [{"id": 1, "price": 100}]


def test_main_respects_custom_out_basename(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Model S", "--out", "my_export"])

    assert (tmp_path / "my_export.csv").exists()
    assert (tmp_path / "my_export.json").exists()
    assert not (tmp_path / "tesla_model-s.csv").exists()


def test_main_prints_summary(fake_scrape, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    scraper.main(["--make", "Tesla", "--model", "Model S"])

    out = capsys.readouterr().out
    assert "Done. 1 unique listings found." in out
    assert "tesla_model-s.csv" in out
    assert "tesla_model-s.json" in out


def test_main_requires_make_and_model(fake_scrape):
    with pytest.raises(SystemExit):
        scraper.main([])


def test_main_rejects_unknown_category(fake_scrape):
    with pytest.raises(SystemExit):
        scraper.main(["--make", "Tesla", "--model", "Model S", "--category", "spaceship"])


# --- run_cli() error-handling / exit codes --------------------------------


def test_run_cli_returns_zero_on_success(fake_scrape, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = scraper.run_cli(["--make", "Tesla", "--model", "Model S"])

    assert exit_code == 0


def test_run_cli_returns_one_and_prints_error_on_value_error(monkeypatch, capsys):
    def boom(argv=None):
        raise ValueError("no such make")

    monkeypatch.setattr(scraper, "main", boom)

    exit_code = scraper.run_cli([])

    assert exit_code == 1
    assert "Error: no such make" in capsys.readouterr().err


def test_run_cli_returns_one_and_prints_message_on_network_error(monkeypatch, capsys):
    def boom(argv=None):
        raise requests.ConnectionError("dns failure")

    monkeypatch.setattr(scraper, "main", boom)

    exit_code = scraper.run_cli([])

    assert exit_code == 1
    assert "Network error talking to autoscout24.ch" in capsys.readouterr().err


def test_run_cli_returns_130_on_keyboard_interrupt(monkeypatch, capsys):
    def boom(argv=None):
        raise KeyboardInterrupt()

    monkeypatch.setattr(scraper, "main", boom)

    exit_code = scraper.run_cli([])

    assert exit_code == 130
    assert "Interrupted" in capsys.readouterr().err


def test_run_cli_does_not_hit_network_before_raising_on_bad_range(tmp_path, monkeypatch):
    # Regression check: an invalid range must fail fast, without resolving
    # make/model or ever creating a requests.Session pointed at the real API.
    monkeypatch.chdir(tmp_path)

    exit_code = scraper.run_cli(
        [
            "--make",
            "Tesla",
            "--model",
            "Model S",
            "--price-from",
            "100",
            "--price-to",
            "50",
        ]
    )

    assert exit_code == 1
    assert not list(tmp_path.iterdir())
