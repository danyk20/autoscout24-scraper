# AutoScout24.ch Scraper

Fetches every listing for a given make/model from autoscout24.ch (Switzerland),
for free — no API key, no token, no paid scraping service.

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

Results are Switzerland-only by construction, since `api.autoscout24.ch` is
the `.ch` domain's own backend.

## Setup

Requires [pipenv](https://pipenv.pypa.io/) (`brew install pipenv` if you
don't have it).

```bash
cd AutoScout
pipenv install
```

## Usage

```bash
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S"
```

This prints progress per search page, then visits every matching listing one
by one to pull full details, and writes two output files in the current
directory: `tesla_model-s.csv` and `tesla_model-s.json`.

### Options

| Flag | Description |
|---|---|
| `--make` | Make name or key, e.g. `Tesla` or `tesla` (required) |
| `--model` | Model name or key, e.g. `"Model S"` or `model-s` (required) |
| `--category` | `car` (default) or `motorcycle` |
| `--out` | Output file base name, without extension. Defaults to `<make>_<model>` |
| `--no-detail` | Skip visiting each listing individually; keep only the summary fields from the search results (faster, fewer fields) |
| `--delay` | Seconds to wait between requests (default `0.4`) — raise this if you get rate-limited |
| `--price-from` / `--price-to` | Filter by price in CHF (inclusive, either end optional) |
| `--mileage-from` / `--mileage-to` | Filter by mileage in km (inclusive, either end optional) |
| `--year-from` / `--year-to` | Filter by first-registration year (inclusive, either end optional) |

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
```

If you mistype a make or model, the script prints a clean error (and for an
unknown model, the list of valid models for that make) instead of crashing.

## Output fields (CSV)

By default (full detail mode) every listing yields around 115 columns,
covering things like: `id, make, model, versionFullName, price,
previousPrice, conditionType, firstRegistrationYear, mileage, fuelType,
transmissionType, horsePower, bodyColor, bodyType, doors, seats, driveType,
batteryCapacity, range, chargingPower, consumption_combined, co2Emission,
vehicleIdentificationNumber, description, features, images, warranty_type,
financing_url, insurance_url, sellerName, sellerType, sellerCity,
sellerZip, url, ...` — plus everything else the detail API happens to
return. Nested objects are flattened to `parent_child` columns; lists
(features, images) are joined into one semicolon-separated cell.

With `--no-detail`, only the ~20 summary fields from the search results are
included (id, make, model, price, mileage, seller, teaser, url, ...).

The JSON file always contains the raw, unflattened API response for each
listing.

## Notes

- Be a reasonable citizen: the default delay between requests is intentional.
  Don't remove it or crank up concurrency — this is an undocumented endpoint
  the site's own frontend uses, not a public API with a stated rate limit.
- If autoscout24.ch changes their API, the `resolve_make_key` /
  `resolve_model_key` / `search_listings` functions are the places to look —
  the module docstring at the top of `autoscout24_scraper.py` documents the
  endpoint shapes in more detail.
