# AutoScout24 Scraper

[![CI](https://github.com/danyk20/autoscout24-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/danyk20/autoscout24-scraper/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/autoscout24-scraper)](https://pypi.org/project/autoscout24-scraper/)
[![Coverage](https://img.shields.io/badge/unit%20test%20coverage-100%25-brightgreen)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)

> Unofficial, independently developed project — not affiliated with, endorsed by, or sponsored by AutoScout24 AG or the Scout24 group. "AutoScout24" is a trademark of its respective owner.

Fetches every listing for a given make/model from AutoScout24 — for free, no API key, no paid scraping service. AutoScout24's HTML pages sit behind Cloudflare bot protection, but their own frontend loads data from a separate, public JSON API that isn't — this scraper talks to that API directly. It defaults to the Swiss site (`autoscout24.ch`); see [docs/REFERENCE.md](docs/REFERENCE.md#domains) for other country domains.

By default it does a two-phase scrape: search to collect every matching listing id, then visit each one individually for the full record (battery/range, dimensions, VIN, images, equipment, description, ...). Every field the API returns is kept — nested objects are flattened into `parent_child` CSV columns, lists are joined into semicolon-separated cells — nothing is silently dropped.

**🤖 Robot-friendly.** This project is explicitly intended to be run, read, imported, or adapted by AI agents and bots, same as a human developer — see [License](#license).

## Setup

Requires [pipenv](https://pipenv.pypa.io/) (`brew install pipenv`).

```bash
git clone https://github.com/danyk20/autoscout24-scraper.git
cd autoscout24-scraper
pipenv install --dev
```

Contributing, linting, and testing commands: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Usage

### CLI

```bash
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S"
```

Prints progress, then writes `tesla_model-s.csv` and `tesla_model-s.json` in the current directory. Installed via `pip install` instead? Drop `pipenv run` — the same command is `autoscout24-scraper --make Tesla --model "Model S"`.

| Flag | Description |
|---|---|
| `--version` | Print the installed version and exit |
| `--make` | Make name or key, e.g. `Tesla` or `tesla` (required) |
| `--model` | Model name or key, e.g. `"Model S"` or `model-s` (required) |
| `--domain` | Country domain (default `ch`) — only `ch` is confirmed to work today, see [docs/REFERENCE.md](docs/REFERENCE.md#domains) |
| `--category` | `car` (default) or `motorcycle` |
| `--out` | Output file base name, without extension. Defaults to `<make>_<model>` |
| `--no-detail` | Skip per-listing detail visits; keep only summary fields (faster, fewer fields) |
| `--delay` | Seconds between requests (default `0.4`) — raise this if you get rate-limited |
| `--price-from` / `--price-to` | Filter by price in CHF (inclusive, either end optional) |
| `--mileage-from` / `--mileage-to` | Filter by mileage in km (inclusive, either end optional) |
| `--year-from` / `--year-to` | Filter by first-registration year (inclusive, either end optional) |
| `-v` / `--verbose` | Also show debug-level detail, including every HTTP request (mutually exclusive with `-q`) |
| `-q` / `--quiet` | Suppress progress output; only warnings/errors (mutually exclusive with `-v`) |

Filters combine with AND and are applied server-side, so they also cut down how many listings get visited in the detail phase. A mistyped make/model prints a clean error (plus, for an unknown model, the list of valid models) instead of crashing.

```bash
# Fast mode: search results only, skip per-listing detail
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --no-detail

# 2018 or newer, under CHF 30'000, under 60'000 km
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --price-to 30000 --year-from 2018 --mileage-to 60000
```

### As a library

```bash
pip install autoscout24-scraper
```

```python
from autoscout24_scraper import scrape

result = scrape("Tesla", "Model S", price_to=30000, year_from=2018)

for row in result.rows:          # list[dict], CSV-ready
    print(row["price"], row["mileage"], row["url"])

result.to_csv("tesla_model_s.csv")  # optional — no files are written unless you ask
```

Full `scrape()` signature, the `ScrapeResult` return type, and the complete JSON/CSV field schema: **[docs/REFERENCE.md](docs/REFERENCE.md)**.

## Testing

```bash
pipenv run pytest                    # unit tests (fast, no network), fails if coverage < 95%
pipenv run pytest -m e2e --no-cov    # end-to-end tests against the real live API
pipenv run pytest -m "e2e or not e2e" --no-cov  # everything
```

Unit tests mock all HTTP (via [`responses`](https://github.com/getsentry/responses)) and cover 100% of `autoscout24_scraper.py`. E2E tests target Tesla Roadster (a small inventory) to confirm the scraper still works against the live site. Coverage detail by area: [docs/REFERENCE.md](docs/REFERENCE.md#test-coverage-by-area).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup and pre-PR checks.

Be a reasonable citizen: the default request delay is intentional — this is an undocumented endpoint the site's own frontend uses, not a public API with a stated rate limit. Don't remove the delay or crank up concurrency.

## License

Released under the [MIT License](LICENSE) — you can use, copy, modify, merge, publish, distribute, and sell copies of this code, for free, for any purpose, commercial or not, as long as the license text stays attached. No warranty.

**AI agents, LLM-based coding assistants, and other bots are explicitly welcome to use this project** — to run the scraper, read and parse its output, import `scrape()` into another project, or read and adapt its source — under exactly the same terms as a human, with no additional restriction and no need to ask permission. That's why [docs/REFERENCE.md](docs/REFERENCE.md) documents the full function signature, return type, and data schema: so a bot can integrate correctly without a human in the loop.

This license does not grant any rights to AutoScout24's own data or terms of service — this project only automates requests to a public, unauthenticated endpoint their own website already calls from any visitor's browser; what you do with the results is between you and them.
