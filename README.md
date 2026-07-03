# AutoScout24 Scraper

[![CI](https://github.com/danyk20/autoscout24-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/danyk20/autoscout24-scraper/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/autoscout24-scraper)](https://pypi.org/project/autoscout24-scraper/)
[![Coverage](https://img.shields.io/badge/unit%20test%20coverage-100%25-brightgreen)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)

> Unofficial, independently developed project. Not affiliated with,
> endorsed by, or sponsored by AutoScout24 AG or the Scout24 group.
> "AutoScout24" is a trademark of its respective owner.

Fetches every listing for a given make/model from AutoScout24, for free — no
API key, no token, no paid scraping service. Defaults to the Swiss site
(`autoscout24.ch`), with an easy-to-use `--domain`/`domain=` override for
other country domains (see [Domains](#domains) below for what's actually
confirmed to work today).

**🤖 This project is robot-friendly.** It is explicitly intended to be used
by AI agents and bots exactly as a human developer would: to run it, read
its output, import it into another project, or adapt its code. It's released
under the very permissive [MIT license](LICENSE) specifically so there is no
ambiguity about that — see [License](#license) below.

## How it works

The autoscout24.ch website is protected by Cloudflare bot detection, which
makes scraping the HTML pages directly (`curl`, `requests`, even headless
Chrome) unreliable.

However, the site's own frontend loads its data from a **separate, public
JSON API** at `api.autoscout24.ch` that is *not* behind that protection and
needs no authentication. This was found by watching the network traffic the
real website makes while searching. The scraper talks to that API directly:

| Endpoint | Purpose |
|---|---|
| `GET /v1/makes` | list of all makes (name + internal key) |
| `GET /v1/makes/key/{make}/models` | list of all models for a make |
| `POST /v1/listings/search` | the search, paginated 20 results at a time — used to collect every listing id |
| `GET /v1/listings/{id}` | full detail record for one listing — visited once per listing by default |

One quirk had to be worked around: without an explicit sort order, the API
rotates a "boosted" listing into the first slot on every request, which
shifts the pagination window and causes some listings to be skipped or
duplicated across pages. The scraper always sorts by price
(`sort: [{"type": "PRICE", "order": "ASC"}]`) to make pagination stable, and
also de-duplicates by listing ID as a safety net.

**Two-phase scraping.** The search endpoint only returns a summary per
listing (~30 fields). To get everything (battery/range, dimensions, VIN,
colors, equipment, full description, every image, ...), the scraper visits
each listing individually, one by one, via its detail endpoint, after the
search phase has collected every id. That's one extra HTTP request per
listing, with a short delay between requests — so a search that matches 173
cars makes 173 extra requests. Use `--no-detail` to skip this and keep only
the fast summary fields.

Every field the API returns for a listing is extracted — nested objects
(seller, financing, consumption, warranty, boot dimensions, ...) are
flattened into `parent_child` columns, and lists (features, images) are
joined into a single semicolon-separated cell — so no data from the API
response is dropped on the way into the CSV.

## Domains

Every function and the CLI accept a `domain` (default `"ch"`), which is
substituted directly into `https://api.autoscout24.{domain}/v1/...` and
`https://www.autoscout24.{domain}/...`.

**As of this writing, `ch` is the only domain confirmed to expose this API.**
AutoScout24's other country sites (`.de`, `.fr`, `.it`, `.be`, `.nl`, `.lu`,
`.es`, ...) resolve and serve pages, but `api.autoscout24.<domain>` doesn't
exist for them (checked by DNS lookup) — they run on a different
product/backend that wasn't reverse-engineered here. Passing e.g.
`--domain de` today will fail with a network/DNS error, not silently return
wrong data.

`domain` exists as a parameter (rather than hardcoding `.ch`) so that:

- if AutoScout24 ever exposes the same `api.autoscout24.<domain>` API for
  another country, this scraper picks it up with zero code changes — just
  pass the new domain;
- if you reverse-engineer another country's API yourself, you don't have to
  fork this project — just call `scrape(..., domain="whatever")` once you've
  confirmed the endpoint shapes match (or adapt the small number of
  domain-aware functions if they don't: `api_base()`, `listing_url()`,
  `resolve_make_key()`, `resolve_model_key()`, `search_listings()`,
  `fetch_detail()`, `visit_all_listings()`).

## Setup

Requires [pipenv](https://pipenv.pypa.io/) (`brew install pipenv` if you
don't have it).

```bash
cd AutoScout
pipenv install --dev
```

(`--dev` also installs the test/lint tooling — pytest, pytest-cov, responses,
ruff, mypy. Leave it off if you only want to run the scraper.)

```bash
pipenv run ruff check .          # lint
pipenv run ruff format --check . # formatting (drop --check to auto-format)
pipenv run mypy autoscout24_scraper.py  # type-check
```

These are exactly the checks the CI workflow (`.github/workflows/ci.yml`)
runs on every push/PR, across Python 3.11 and 3.12.

## Usage

The scraper works two ways: as a standalone CLI script that writes files, or
as a library you import into another project to get the data back directly.

### As a CLI script

```bash
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S"
```

(If you installed the package via `pip install` instead, as described in the
"as a library" section below, the same command is just
`autoscout24-scraper --make Tesla --model "Model S"` — no `pipenv run`
needed.)

This prints progress per search page, then visits every matching listing one
by one to pull full details, and writes two output files in the current
directory: `tesla_model-s.csv` and `tesla_model-s.json`.

### Options

| Flag | Description |
|---|---|
| `--version` | Print the installed version and exit |
| `--make` | Make name or key, e.g. `Tesla` or `tesla` (required) |
| `--model` | Model name or key, e.g. `"Model S"` or `model-s` (required) |
| `--domain` | Country domain, matching `autoscout24.<domain>` (default `ch`). Only `ch` is confirmed to work today — see [Domains](#domains) |
| `--category` | `car` (default) or `motorcycle` |
| `--out` | Output file base name, without extension. Defaults to `<make>_<model>` |
| `--no-detail` | Skip visiting each listing individually; keep only the summary fields from the search results (faster, fewer fields) |
| `--delay` | Seconds to wait between requests (default `0.4`) — raise this if you get rate-limited |
| `--price-from` / `--price-to` | Filter by price in CHF (inclusive, either end optional) |
| `--mileage-from` / `--mileage-to` | Filter by mileage in km (inclusive, either end optional) |
| `--year-from` / `--year-to` | Filter by first-registration year (inclusive, either end optional) |
| `-v` / `--verbose` | Also show debug-level detail, including every HTTP request made (mutually exclusive with `-q`) |
| `-q` / `--quiet` | Suppress progress output; only warnings/errors are shown (mutually exclusive with `-v`) |

All three filters are optional and combine with AND. They're applied by the
search API itself (not filtered client-side afterwards), so they also cut
down how many listings get visited in the detail phase.

### Examples

```bash
# Full run: search + visit every listing for full details (default)
pipenv run python autoscout24_scraper.py --make Tesla --model "Model 3"

# Custom output filename
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --out my_search

# Fast mode: search results only, skip visiting each listing
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --no-detail

# Only cars under CHF 30'000
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --price-to 30000

# 2018 or newer, under 60'000 km
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --year-from 2018 --mileage-to 60000

# Price range plus year range together
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --price-from 20000 --price-to 50000 --year-from 2019

# Any make/model works
pipenv run python autoscout24_scraper.py --make BMW --model "M3"

# Explicit domain (defaults to "ch" — see Domains section for what else works today)
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --domain ch
```

If you mistype a make or model, the script prints a clean error (and for an
unknown model, the list of valid models for that make) instead of crashing.

### As a library, from another project

Import `scrape()` and call it directly — it does the same work as the CLI
(search, then visit every listing for full detail) but returns a
`ScrapeResult` object instead of writing files. No files are written unless
you explicitly ask for them.

```python
from autoscout24_scraper import scrape

result = scrape("Tesla", "Model S", price_to=30000, year_from=2018)

result.rows       # list[dict]: one flattened dict per listing, CSV-ready
result.listings   # list[dict]: raw (unflattened) API JSON per listing, each with a "url" field
result.make_name, result.model_name, result.total_elements, result.domain

for row in result.rows:
    print(row["price"], row["mileage"], row["url"])

# Optional: write to disk anyway, e.g. for a one-off export
result.to_csv("tesla_model_s.csv")
result.to_json("tesla_model_s.json")
```

This section is the authoritative reference for the return types — both for
a human integrating this into another project, and for an AI agent that
needs to know exactly what it's going to get back without having to read
the whole source file.

#### `scrape()` signature

```python
def scrape(
    make: str,                       # e.g. "Tesla" or "tesla" — name or key, case-insensitive
    model: str,                      # e.g. "Model S" or "model-s" — name or key, case-insensitive
    *,
    domain: str = "ch",              # autoscout24.<domain>; only "ch" confirmed to work today
    category: str = "car",           # "car" or "motorcycle"
    detail: bool = True,             # visit every listing individually for full fields (slower)
    price_from: int | None = None,   # CHF, inclusive
    price_to: int | None = None,     # CHF, inclusive
    mileage_from: int | None = None, # km, inclusive
    mileage_to: int | None = None,   # km, inclusive
    year_from: int | None = None,    # first-registration year, inclusive
    year_to: int | None = None,      # first-registration year, inclusive
    delay: float = 0.4,              # seconds between HTTP requests
    verbose: bool = True,            # emit progress via the "autoscout24_scraper" logger at INFO level
    session: requests.Session | None = None,  # reuse a session across calls if given
) -> ScrapeResult:
    ...
```

Raises `ValueError` immediately (before any network call) if any `_from` is
greater than its `_to`. Raises `requests.RequestException` subclasses on
unrecoverable network errors, and `ValueError` if `make`/`model` can't be
resolved (the message lists valid models for an unknown-model error).

**Logging.** Library code never configures logging itself (no
`basicConfig`, no handlers) — it only emits through
`logging.getLogger("autoscout24_scraper")`, same as any well-behaved
library. That means if you call `scrape()` from your own script with no
logging configuration of your own, `verbose=True`'s progress messages exist
but won't be visible anywhere, by design — Python's standard "libraries
don't talk unless you ask them to" behavior. To see them:

```python
import logging
logging.basicConfig(level=logging.INFO)  # now scrape()'s progress is visible
```

The CLI is the one place that *does* configure real handlers automatically
(see `--verbose`/`--quiet` below) — that's the only difference between
running this as a script versus importing it.

#### `ScrapeResult` — the return value

```python
@dataclass
class ScrapeResult:
    make_key: str          # resolved make key, e.g. "tesla"
    make_name: str         # resolved make display name, e.g. "TESLA"
    model_key: str         # resolved model key, e.g. "model-s"
    model_name: str        # resolved model display name, e.g. "MODEL S"
    category: str          # "car" or "motorcycle", as requested
    total_elements: int    # number of unique listings found by the search phase
    listings: list[dict]   # raw API objects — see "Data structure" below
    rows: list[dict]       # flattened dicts, one per listing, CSV-ready, sorted by price ascending
    domain: str            # domain that was scraped, e.g. "ch"

    def to_csv(self, path: str) -> None: ...   # writes self.rows
    def to_json(self, path: str) -> None: ...  # writes self.listings
```

`len(result.rows) == len(result.listings) == result.total_elements` always
holds (barring `--no-detail`/`detail=False`, where they still match — detail
mode only adds fields, it never drops or adds listings).

Install it into your own project's environment with:

```bash
pip install autoscout24-scraper
```

(Not yet published? Install the latest unreleased code straight from GitHub
instead: `pip install git+https://github.com/danyk20/autoscout24-scraper.git`.)

Either way you also get a real `autoscout24-scraper` command (see
`--version` below), not just the importable module — pipenv is only needed
if you're working on this repo itself (running its CLI from source, or its
test suite).

## Data structure

This section documents exactly what's in the output — precisely enough that
a developer or an AI agent can parse it without having to run the scraper
first and reverse-engineer the shape themselves.

### JSON (`result.listings` / the `.json` file)

The JSON file (and `ScrapeResult.listings`) is a **JSON array of listing
objects**, one per vehicle found. Every listing object always includes:

| Field | Type | Description |
|---|---|---|
| `id` | `int` | AutoScout24's internal listing id |
| `url` | `string` | **Full URL of the original ad** on autoscout24.\<domain\>, e.g. `https://www.autoscout24.ch/de/d/12906672` — added by this scraper (the raw API response does not include it), so you can always click straight back to the source listing |
| `make` | `object` | `{"id": int, "key": string, "name": string}`, e.g. `{"id": 391, "key": "tesla", "name": "TESLA"}` |
| `model` | `object` | Same shape as `make`, for the model |
| `price` | `number \| null` | Asking price in the local currency (CHF for `.ch`) |
| `mileage` | `int \| null` | Kilometers |
| `firstRegistrationYear` | `int \| null` | |
| `fuelType`, `transmissionType`, `conditionType` | `string \| null` | Free-form category strings AutoScout24 uses internally (e.g. `"electric"`, `"automatic"`, `"used"`) |

There are two possible **shapes** for the rest of the object, depending on
whether detail mode ran:

- **Summary shape** (`detail=False` / `--no-detail`): ~30 fields, exactly
  what the search endpoint returns — includes a nested `seller` object
  (`{"name", "type", "city", "zipCode", "id", ...}`) but no VIN, no
  dimensions, no description.
- **Detail shape** (`detail=True`, the default): ~90 fields from the
  per-listing detail endpoint — adds `description` (`string|null`),
  `vehicleIdentificationNumber` (`string|null`, the VIN), `bodyColor`,
  `bodyType`, `doors`, `seats`, `driveType`, dimensions (`length`, `width`,
  `height`, `weightCurb`, `weightTotal`, all `int|null`, in mm/kg), EV
  specs (`batteryCapacity`, `range`, `chargingPower`, ... `float|int|null`),
  `warranty` (`object`), `images` (`list[{"key": string}]` — each `key` is a
  path under `https://listing-images.autoscout24.<domain>/`), `features`
  (`list[{"feature": string}]`), `financing`/`insurance` (`object` with a
  `url`), and more. In this shape, `seller` collapses to a bare `sellerId`
  (`int`) — the detail endpoint doesn't return the seller's name/city/zip,
  so `visit_all_listings()` copies the `seller` object over from the search
  summary before overwriting the record, keeping it available either way.

There is no fixed/versioned schema published by AutoScout24 for these
objects — the tables above reflect the fields observed in practice as of
this writing. Treat unknown/missing fields defensively (`.get(...)`, not
`[...]`) since AutoScout24 can add or omit fields per listing.

### CSV (`result.rows` / the `.csv` file)

The CSV is a **flattened** version of the same data — one row per listing,
same rows/listings correspondence and order. Flattening rules (also
available programmatically as `flatten_listing()`):

- Nested objects become `parent_child` columns, e.g. `financing.url` →
  `financing_url`, `warranty.type` → `warranty_type`.
- `make`/`model` become two columns each: `make`/`makeKey`,
  `model`/`modelKey`.
- `seller` becomes `sellerName`, `sellerType`, `sellerCity`, `sellerZip`.
- Lists are joined into one semicolon-separated cell, e.g. `features` →
  `"top-list; premium"`, `images` → the semicolon-joined list of image keys.
- `url` is always present as its own column (same value as the JSON `url`
  field described above).
- Columns are the union of every field seen across all rows (heterogeneous
  listings don't crash the writer — missing values are an empty string),
  with `id, make, model, versionFullName, price, previousPrice,
  conditionType, firstRegistrationYear, mileage, fuelType,
  transmissionType, horsePower, sellerName, sellerType, sellerCity,
  sellerZip, url` pinned first and everything else sorted alphabetically
  after them.

In full detail mode (the default) this is around 115-120 columns; with
`--no-detail`/`detail=False` it's around 20.

## Testing

The CI badge above is live (it reflects the actual state of the most recent
GitHub Actions run). The coverage badge is a static snapshot of the last
verified `pytest` run, not wired to a live coverage service — enforced
locally and in CI via the `--cov-fail-under=95` gate described below, so it
can't silently drop without the build going red.

The test suite lives in `tests/` and is split into two kinds of tests:

- **Unit tests** (`tests/test_*.py`, excluding `test_e2e.py`) — every
  function is tested in isolation with HTTP mocked out (via the
  [`responses`](https://github.com/getsentry/responses) library), so they
  run in well under a second, need no network access, and never touch
  the real site. This is the default `pytest` run.
- **End-to-end tests** (`tests/test_e2e.py`) — make real calls against
  `api.autoscout24.ch`. They're marked `@pytest.mark.e2e` and excluded by
  default; run them explicitly when you want to confirm the scraper still
  works against the live API (e.g. after autoscout24.ch changes something).
  They target Tesla Roadster specifically because its inventory is small
  (order of ~10 listings), so the full detail-visiting pipeline and a real
  CLI subprocess run both complete in a few seconds without hammering the
  API.

```bash
# Unit tests only (fast, no network) — this is what `pytest` runs by default.
# Also prints a coverage report and fails the run if coverage drops below 95%.
pipenv run pytest

# End-to-end tests only (real network calls, several seconds)
pipenv run pytest -m e2e --no-cov

# Everything
pipenv run pytest -m "e2e or not e2e" --no-cov

# HTML coverage report you can open in a browser
pipenv run pytest --cov-report=html && open htmlcov/index.html
```

The unit suite covers 100% of `autoscout24_scraper.py` (the two lines
excluded via `# pragma: no cover` are a defensive "unreachable" guard in the
retry loop, and the `if __name__ == "__main__":` guard itself, which is
exercised for real by the e2e suite's CLI subprocess tests instead).

What's covered:

| Area | Unit tests | E2E tests |
|---|---|---|
| `request_with_retries` | retry-then-succeed and exhausted-retries paths for 429/5xx/connection errors, no retry on 4xx | — |
| `resolve_make_key` / `resolve_model_key` | exact key, exact name, substring fallback, not-found errors, category param, custom `domain` | real lookups (`Tesla`, `Roadster`), unknown-make error |
| `search_listings` | pagination + de-dup, stable sort, every filter combination, verbose on/off, custom `domain`, embedded `url` | real result count, real filter narrowing |
| `fetch_detail` / `visit_all_listings` | seller backfill, progress printing, per-request delay, custom `domain`, embedded `url` | real detail fetch |
| `flatten_listing` / `_scalarize` / `order_fieldnames` | every branch (nested dicts, lists, missing/unrecognized types) | implicitly, via real data |
| `save_csv` / `save_json` / `ScrapeResult` | heterogeneous rows, unicode, empty input | round-trip against real files |
| `scrape()` | orchestration, range validation, filter/session pass-through, sorting | full real pipeline, with and without `--detail` |
| `main()` / `run_cli()` | every CLI flag, default vs. custom output filenames, all three exit-code paths | real subprocess run, real error exit code |

## Notes

- Be a reasonable citizen: the default delay between requests is intentional.
  Don't remove it or crank up concurrency — this is an undocumented endpoint
  the site's own frontend uses, not a public API with a stated rate limit.
- If autoscout24.ch changes their API, the `resolve_make_key` /
  `resolve_model_key` / `search_listings` functions are the places to look —
  the module docstring at the top of `autoscout24_scraper.py` documents the
  endpoint shapes in more detail. Run the e2e suite after any such change to
  confirm the fix.

## License

This project is released under the [MIT License](LICENSE) — one of the most
permissive open-source licenses that exist. In plain terms: you can use,
copy, modify, merge, publish, distribute, and even sell copies of this code,
for free, for any purpose, commercial or not, as long as the license text
stays attached. There is no warranty.

**AI agents, LLM-based coding assistants, and other bots are explicitly
welcome to use this project** — to run the scraper, to read and parse its
output, to import `scrape()` into another project, or to read and adapt its
source code — under exactly the same terms as a human would, with no
additional restriction and no need to ask permission. That's the whole
point of the fully-typed [`scrape()` signature and `ScrapeResult`
reference](#as-a-library-from-another-project) and the [Data
structure](#data-structure) section above: so a bot reading this file can
integrate with the code correctly without a human in the loop, same as a
person reading it would.

The one thing this permissive license does *not* do is grant any rights to
AutoScout24's own data or terms of service — this project only automates
requests to a public, unauthenticated endpoint their own website already
calls from any visitor's browser; what you do with the results is between
you and them.
