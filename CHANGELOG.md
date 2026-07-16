# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-16

### Changed

- Minimum supported Python bumped to 3.13 (dropping 3.11 and 3.12); CI,
  ruff, and mypy target-version updated to match. **Breaking:** installs
  on Python 3.11/3.12 will no longer work.

### Fixed

- `resolve_model_key()` no longer raises when a model query is a more
  specific trim/variant than any listed model name (e.g. `"Model
  S90D"` for Tesla's `"MODEL S"` line). It now falls back to the
  closest listed model whose name/key is a prefix of the query, logging
  a warning instead of erroring.

## [0.1.0] - 2026-07-03

Initial release.

### Added

- Scraper for autoscout24.ch vehicle listings, usable both as a CLI
  (`autoscout24-scraper` / `python autoscout24_scraper.py`) and as a
  library (`from autoscout24_scraper import scrape`).
- Search by any make/model (resolved dynamically against the site's own
  lookup endpoints, not a hardcoded list), with optional price/mileage/
  first-registration-year range filters.
- Full-detail mode (default): visits every matching listing individually
  to extract every field the detail API returns, generically flattened
  for CSV output; `--no-detail`/`detail=False` for a faster summary-only
  pass.
- Every listing's raw JSON and flattened CSV row both carry a direct
  `url` back to the original ad.
- `domain` parameter (default `"ch"`) so the API host/ad URLs are not
  hardcoded to Switzerland, in case AutoScout24 exposes the same API
  shape for another country in the future.
- `ScrapeResult` dataclass return value (`.rows`, `.listings`,
  `.to_csv()`, `.to_json()`) for library use, with the CLI as a thin
  wrapper around the same `scrape()` function.
- Console script entry point (`autoscout24-scraper`) and `pip install`
  support via `pyproject.toml` packaging metadata; `--version` flag.
- Logging-based output (`-v`/`--verbose`, `-q`/`--quiet`) instead of bare
  `print()`, so library consumers can configure/suppress it via the
  standard `logging` module.
- Full type hints throughout, checked with mypy; linted and formatted
  with Ruff.
- Unit test suite (100% coverage, all HTTP mocked) plus a smaller
  end-to-end suite against the real live API, run on a separate weekly
  GitHub Actions schedule.
- CI (GitHub Actions) running lint, type-check, and the unit suite on
  every push/PR across Python 3.11 and 3.12.
- MIT license with an explicit statement welcoming AI agents/bots to use
  the project under the same terms as a human developer.
- Project governance docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, issue/PR templates.
