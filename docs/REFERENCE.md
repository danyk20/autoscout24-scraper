# Reference

Full API surface, return types, and data schema for anyone integrating with
this project as a library — a human developer or an AI agent — without
reading the source. See [README.md](../README.md) for the pitch, install,
and CLI usage.

## Domains

Every function and the CLI accept a `domain` (default `"ch"`), substituted
directly into `https://api.autoscout24.{domain}/v1/...` and
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

## How the API is discovered and used

The public `api.autoscout24.ch` API isn't documented by AutoScout24 — it was
found by watching the network traffic the real website makes while
searching, and is the same API the site's own frontend calls (not behind
Cloudflare bot protection, unlike the HTML pages).

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

## `scrape()` signature

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
(`--verbose`/`--quiet`) — that's the only difference between running this as
a script versus importing it.

## `ScrapeResult` — the return value

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

## Data structure

### JSON (`result.listings` / the `.json` file)

A **JSON array of listing objects**, one per vehicle found. Every listing
object always includes:

| Field | Type | Description |
|---|---|---|
| `id` | `int` | AutoScout24's internal listing id |
| `url` | `string` | **Full URL of the original ad**, e.g. `https://www.autoscout24.ch/de/d/12906672` — added by this scraper (the raw API response does not include it) |
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

## Test coverage by area

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

The unit suite covers 100% of `autoscout24_scraper.py` (the two lines
excluded via `# pragma: no cover` are a defensive "unreachable" guard in the
retry loop, and the `if __name__ == "__main__":` guard itself, which is
exercised for real by the e2e suite's CLI subprocess tests instead).
