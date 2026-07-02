#!/usr/bin/env python3
"""
AutoScout24.ch vehicle listing scraper.

Uses the public, unauthenticated JSON API that the autoscout24.ch website itself
calls from the browser (api.autoscout24.ch). No API key, no token, no paid
scraping service required.

Discovered endpoints:
  GET  https://api.autoscout24.ch/v1/makes?vehicleCategory=car
       -> list of {id, key, name} for every make
  GET  https://api.autoscout24.ch/v1/makes/key/{makeKey}/models?vehicleCategory=car
       -> list of {id, key, name, group} for every model of a make
  POST https://api.autoscout24.ch/v1/listings/search
       body: {"query": {...filters...}, "pagination": {"page": N, "size": 20}}
       -> {"content": [...listings...], "totalElements", "totalPages", ...}
  GET  https://api.autoscout24.ch/v1/listings/{id}
       -> full detail record for one listing

Pagination is fixed at size=20 per page (other sizes return 400). The API
sometimes reshuffles a "top-list" (boosted/sponsored) listing into position 0,
so listings are de-duplicated by id while paging.

After the search phase collects every listing id, the scraper visits each
listing's detail endpoint one by one (GET /v1/listings/{id}) and extracts
every field it returns (not just the summary fields from the search
response). This is slower (one request per listing) but gives full specs:
battery/range, dimensions, VIN, colors, equipment, description, etc.

Optional range filters (price, mileage, first-registration year) map
directly onto the search API's own filters: priceFrom/priceTo,
mileageFrom/mileageTo, firstRegistrationYearFrom/firstRegistrationYearTo.

Usage:
    python3 autoscout24_scraper.py --make tesla --model model-s
    python3 autoscout24_scraper.py --make "Tesla" --model "Model S" --out tesla_model_s
    python3 autoscout24_scraper.py --make tesla --model model-s --no-detail   # skip per-listing detail fetch (faster, fewer fields)
    python3 autoscout24_scraper.py --make tesla --model model-s --price-to 30000 --year-from 2018
"""
import argparse
import csv
import json
import sys
import time
from urllib.parse import quote

import requests

API_BASE = "https://api.autoscout24.ch/v1"
PAGE_SIZE = 20
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
}


def make_session():
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def request_with_retries(session, method, url, *, max_retries=5, backoff=1.5, **kwargs):
    kwargs.setdefault("timeout", 20)
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            if attempt == max_retries:
                raise
            wait = backoff ** attempt
            print(f"  [warn] {method} {url} failed ({exc}); retry {attempt}/{max_retries} in {wait:.1f}s",
                  file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries:
                resp.raise_for_status()
            wait = backoff ** attempt
            print(f"  [warn] {method} {url} -> {resp.status_code}; retry {attempt}/{max_retries} in {wait:.1f}s",
                  file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError("unreachable")


def resolve_make_key(session, make_query, vehicle_category="car"):
    """Accepts either an exact key (e.g. 'tesla') or a human name (e.g. 'Tesla')."""
    resp = request_with_retries(session, "GET", f"{API_BASE}/makes",
                                 params={"vehicleCategory": vehicle_category})
    makes = resp.json()
    q = make_query.strip().lower()
    for m in makes:
        if m["key"].lower() == q:
            return m["key"], m["name"]
    for m in makes:
        if m["name"].lower() == q:
            return m["key"], m["name"]
    for m in makes:
        if q in m["name"].lower() or q in m["key"].lower():
            return m["key"], m["name"]
    raise ValueError(f"Could not find a make matching {make_query!r}")


def resolve_model_key(session, make_key, model_query, vehicle_category="car"):
    resp = request_with_retries(session, "GET", f"{API_BASE}/makes/key/{quote(make_key)}/models",
                                 params={"vehicleCategory": vehicle_category})
    models = resp.json()
    q = model_query.strip().lower()
    for m in models:
        if m["key"].lower() == q:
            return m["key"], m["name"]
    for m in models:
        if m["name"].lower() == q:
            return m["key"], m["name"]
    for m in models:
        if q in m["name"].lower() or q in m["key"].lower():
            return m["key"], m["name"]
    available = ", ".join(sorted(m["name"] for m in models))
    raise ValueError(f"Could not find a model matching {model_query!r} for make {make_key!r}. "
                      f"Available models: {available}")


def search_listings(session, make_key, model_key, vehicle_category="car", delay=0.4, verbose=True,
                     price_from=None, price_to=None, mileage_from=None, mileage_to=None,
                     year_from=None, year_to=None):
    """Fetch every listing for a given make/model, deduplicated by id.

    Sorting explicitly by price is important: with no sort specified, the API
    injects a rotating "top-list" (boosted) listing at position 0 on every
    request, which shifts the rest of the page window and causes listings to
    be skipped or duplicated across pages. A stable sort makes pagination
    deterministic and yields the full result set.

    price_from/price_to, mileage_from/mileage_to and year_from/year_to are
    all optional and map directly onto the API's own range filters
    (priceFrom/priceTo, mileageFrom/mileageTo,
    firstRegistrationYearFrom/firstRegistrationYearTo). Leave any of them as
    None to not filter on that dimension.
    """
    query = {
        "vehicleCategories": [vehicle_category],
        "makeModelVersions": [{"makeKey": make_key, "modelKey": model_key}],
    }
    if price_from is not None:
        query["priceFrom"] = price_from
    if price_to is not None:
        query["priceTo"] = price_to
    if mileage_from is not None:
        query["mileageFrom"] = mileage_from
    if mileage_to is not None:
        query["mileageTo"] = mileage_to
    if year_from is not None:
        query["firstRegistrationYearFrom"] = year_from
    if year_to is not None:
        query["firstRegistrationYearTo"] = year_to
    sort = [{"type": "PRICE", "order": "ASC"}]

    seen_ids = set()
    listings = []

    page = 0
    total_pages = 1
    total_elements = None
    while page < total_pages:
        body = {"query": query, "sort": sort, "pagination": {"page": page, "size": PAGE_SIZE}}
        resp = request_with_retries(session, "POST", f"{API_BASE}/listings/search", json=body)
        data = resp.json()
        total_pages = data.get("totalPages", 1)
        total_elements = data.get("totalElements", total_elements)
        content = data.get("content", [])

        new_count = 0
        for item in content:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                listings.append(item)
                new_count += 1

        if verbose:
            print(f"  page {page + 1}/{total_pages}: {len(content)} listings "
                  f"({new_count} new, {len(listings)} total so far)")

        page += 1
        if page < total_pages:
            time.sleep(delay)

    if verbose and total_elements is not None:
        print(f"  API reports {total_elements} total matches; collected {len(listings)} unique listings")

    return listings


def fetch_detail(session, listing_id):
    resp = request_with_retries(session, "GET", f"{API_BASE}/listings/{listing_id}")
    return resp.json()


def visit_all_listings(session, listings, delay=0.4, verbose=True):
    """Visit each listing's detail endpoint one by one and merge the result.

    The detail endpoint (GET /v1/listings/{id}) returns far more fields than
    the search endpoint (battery/range, dimensions, VIN, colors, equipment,
    description, ...) but drops the seller name/city/zip/type down to a bare
    sellerId, so we keep whatever the search response already had for that.
    """
    visited = []
    total = len(listings)
    for i, item in enumerate(listings, 1):
        listing_id = item["id"]
        detail = fetch_detail(session, listing_id)
        if "seller" in item:
            detail.setdefault("seller", item["seller"])
        visited.append(detail)
        if verbose and (i % 10 == 0 or i == total):
            print(f"  visited {i}/{total} listings (id={listing_id})")
        if i < total:
            time.sleep(delay)
    return visited


def listing_url(listing_id):
    return f"https://www.autoscout24.ch/de/d/{listing_id}"


# Fields worth pulling to the front of the CSV; everything else discovered on
# the listing objects is appended afterwards, sorted alphabetically, so no
# field the API returns is ever silently dropped.
PRIORITY_FIELDS = [
    "id", "make", "model", "versionFullName", "price", "previousPrice",
    "conditionType", "firstRegistrationYear", "mileage", "fuelType",
    "transmissionType", "horsePower", "sellerName", "sellerType",
    "sellerCity", "sellerZip", "url",
]


def _scalarize(value):
    """Turn a nested dict/list value into something that fits one CSV cell."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        # A handful of nested objects have an obvious "main" field.
        for key in ("name", "feature", "key", "providerName", "type"):
            if key in value and not isinstance(value[key], (dict, list)):
                return value[key]
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        return "; ".join(str(_scalarize(v)) for v in value)
    return str(value)


def flatten_listing(item):
    """Flatten a listing (search-result or full-detail shape) into one flat
    dict covering every field the API returned for it, so nothing is lost."""
    flat = {}
    for key, value in item.items():
        if key == "seller" and isinstance(value, dict):
            flat["sellerName"] = value.get("name")
            flat["sellerType"] = value.get("type")
            flat["sellerCity"] = value.get("city")
            flat["sellerZip"] = value.get("zipCode")
            continue
        if key in ("make", "model") and isinstance(value, dict):
            flat[key] = value.get("name")
            flat[f"{key}Key"] = value.get("key")
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}_{sub_key}"] = _scalarize(sub_value)
            continue
        flat[key] = _scalarize(value)
    flat["url"] = listing_url(item.get("id"))
    return flat


def order_fieldnames(all_keys):
    ordered = [f for f in PRIORITY_FIELDS if f in all_keys]
    remaining = sorted(k for k in all_keys if k not in ordered)
    return ordered + remaining


def save_csv(rows, path):
    if not rows:
        print("  [warn] no rows to write")
        return
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    fieldnames = order_fieldnames(all_keys)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)


def save_json(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Scrape autoscout24.ch listings for a given make/model.")
    parser.add_argument("--make", required=True, help="Make name or key, e.g. 'Tesla' or 'tesla'")
    parser.add_argument("--model", required=True, help="Model name or key, e.g. 'Model S' or 'model-s'")
    parser.add_argument("--category", default="car", choices=["car", "motorcycle"],
                         help="Vehicle category (default: car)")
    parser.add_argument("--out", default=None, help="Output file base name (without extension). "
                                                      "Defaults to '<make>_<model>' in the current directory.")
    parser.add_argument("--no-detail", action="store_true",
                         help="Skip visiting each listing's detail page; keep only the summary "
                              "fields from the search results (faster, fewer fields).")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay in seconds between requests.")
    parser.add_argument("--price-from", type=int, default=None, help="Minimum price in CHF (inclusive).")
    parser.add_argument("--price-to", type=int, default=None, help="Maximum price in CHF (inclusive).")
    parser.add_argument("--mileage-from", type=int, default=None, help="Minimum mileage in km (inclusive).")
    parser.add_argument("--mileage-to", type=int, default=None, help="Maximum mileage in km (inclusive).")
    parser.add_argument("--year-from", type=int, default=None,
                         help="Earliest first-registration year (inclusive).")
    parser.add_argument("--year-to", type=int, default=None,
                         help="Latest first-registration year (inclusive).")
    args = parser.parse_args()

    for lo_name, hi_name, lo, hi in (
        ("--price-from", "--price-to", args.price_from, args.price_to),
        ("--mileage-from", "--mileage-to", args.mileage_from, args.mileage_to),
        ("--year-from", "--year-to", args.year_from, args.year_to),
    ):
        if lo is not None and hi is not None and lo > hi:
            raise ValueError(f"{lo_name} ({lo}) cannot be greater than {hi_name} ({hi})")

    session = make_session()

    print(f"Resolving make {args.make!r} ...")
    make_key, make_name = resolve_make_key(session, args.make, args.category)
    print(f"  -> make key={make_key!r} name={make_name!r}")

    print(f"Resolving model {args.model!r} for make {make_name!r} ...")
    model_key, model_name = resolve_model_key(session, make_key, args.model, args.category)
    print(f"  -> model key={model_key!r} name={model_name!r}")

    active_filters = []
    if args.price_from is not None or args.price_to is not None:
        active_filters.append(f"price {args.price_from or 0}-{args.price_to or '∞'} CHF")
    if args.mileage_from is not None or args.mileage_to is not None:
        active_filters.append(f"mileage {args.mileage_from or 0}-{args.mileage_to or '∞'} km")
    if args.year_from is not None or args.year_to is not None:
        active_filters.append(f"year {args.year_from or '…'}-{args.year_to or '…'}")
    filter_note = f" [filters: {', '.join(active_filters)}]" if active_filters else ""

    print(f"Fetching listings for {make_name} {model_name} (Switzerland, autoscout24.ch){filter_note} ...")
    raw_listings = search_listings(
        session, make_key, model_key, args.category, delay=args.delay,
        price_from=args.price_from, price_to=args.price_to,
        mileage_from=args.mileage_from, mileage_to=args.mileage_to,
        year_from=args.year_from, year_to=args.year_to,
    )

    if not args.no_detail:
        print(f"Visiting each of {len(raw_listings)} listings one by one to extract full details ...")
        raw_listings = visit_all_listings(session, raw_listings, delay=args.delay)

    rows = [flatten_listing(item) for item in raw_listings]
    rows.sort(key=lambda r: (r.get("price") in (None, ""), r.get("price")))

    out_base = args.out or f"{make_key}_{model_key}"
    csv_path = f"{out_base}.csv"
    json_path = f"{out_base}.json"
    save_csv(rows, csv_path)
    save_json(raw_listings, json_path)

    print(f"\nDone. {len(rows)} unique listings found.")
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error talking to autoscout24.ch: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
