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
| `POST /v1/listings/search` | the actual search, paginated 20 results at a time |
| `GET /v1/listings/{id}` | full detail record for one listing (used only with `--detail`) |

One quirk had to be worked around: without an explicit sort order, the API
rotates a "boosted" listing into the first slot on every request, which
shifts the pagination window and causes some listings to be skipped or
duplicated across pages. The scraper always sorts by price
(`sort: [{"type": "PRICE", "order": "ASC"}]`) to make pagination stable, and
also de-duplicates by listing ID as a safety net.

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

This prints progress per page and writes two output files in the current
directory: `tesla_model-s.csv` and `tesla_model-s.json`.

### Options

| Flag | Description |
|---|---|
| `--make` | Make name or key, e.g. `Tesla` or `tesla` (required) |
| `--model` | Model name or key, e.g. `"Model S"` or `model-s` (required) |
| `--category` | `car` (default) or `motorcycle` |
| `--out` | Output file base name, without extension. Defaults to `<make>_<model>` |
| `--detail` | Fetch the full technical detail record for every listing (one extra request per car — slower, more fields, e.g. battery capacity, VIN, dimensions) |
| `--delay` | Seconds to wait between requests (default `0.4`) — raise this if you get rate-limited |

### Examples

```bash
# Basic search
pipenv run python autoscout24_scraper.py --make Tesla --model "Model 3"

# Custom output filename
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --out my_search

# Full technical detail per listing (slower)
pipenv run python autoscout24_scraper.py --make Tesla --model "Model S" --detail

# Any make/model works
pipenv run python autoscout24_scraper.py --make BMW --model "M3"
```

If you mistype a make or model, the script prints a clean error (and for an
unknown model, the list of valid models for that make) instead of crashing.

## Output fields (CSV)

`id, make, model, version, price_chf, previous_price_chf,
first_registration_year, mileage_km, fuel_type, transmission_type,
horse_power, condition, had_accident, inspected, seller_name, seller_type,
seller_city, seller_zip, teaser, url`

The JSON file contains the raw, unflattened API response for each listing
(more fields, e.g. images, financing/insurance links).

## Notes

- Be a reasonable citizen: the default delay between requests is intentional.
  Don't remove it or crank up concurrency — this is an undocumented endpoint
  the site's own frontend uses, not a public API with a stated rate limit.
- If autoscout24.ch changes their API, the `resolve_make_key` /
  `resolve_model_key` / `search_listings` functions are the places to look —
  the module docstring at the top of `autoscout24_scraper.py` documents the
  endpoint shapes in more detail.
