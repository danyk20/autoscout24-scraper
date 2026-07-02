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

Usage:
    python3 autoscout24_scraper.py --make tesla --model model-s
    python3 autoscout24_scraper.py --make "Tesla" --model "Model S" --out tesla_model_s
    python3 autoscout24_scraper.py --make tesla --model model-s --detail   # fetch full detail per listing (slower)
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


def search_listings(session, make_key, model_key, vehicle_category="car", delay=0.4, verbose=True):
    """Fetch every listing for a given make/model, deduplicated by id.

    Sorting explicitly by price is important: with no sort specified, the API
    injects a rotating "top-list" (boosted) listing at position 0 on every
    request, which shifts the rest of the page window and causes listings to
    be skipped or duplicated across pages. A stable sort makes pagination
    deterministic and yields the full result set.
    """
    query = {
        "vehicleCategories": [vehicle_category],
        "makeModelVersions": [{"makeKey": make_key, "modelKey": model_key}],
    }
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


def listing_url(listing_id):
    return f"https://www.autoscout24.ch/de/d/{listing_id}"


def flatten_listing(item):
    make = item.get("make") or {}
    model = item.get("model") or {}
    seller = item.get("seller") or {}
    return {
        "id": item.get("id"),
        "make": make.get("name"),
        "model": model.get("name"),
        "version": item.get("versionFullName"),
        "price_chf": item.get("price"),
        "previous_price_chf": item.get("previousPrice"),
        "first_registration_year": item.get("firstRegistrationYear"),
        "mileage_km": item.get("mileage"),
        "fuel_type": item.get("fuelType"),
        "transmission_type": item.get("transmissionType"),
        "horse_power": item.get("horsePower"),
        "condition": item.get("conditionType"),
        "had_accident": item.get("hadAccident"),
        "inspected": item.get("inspected"),
        "seller_name": seller.get("name"),
        "seller_type": seller.get("type"),
        "seller_city": seller.get("city"),
        "seller_zip": seller.get("zipCode"),
        "teaser": item.get("teaser"),
        "url": listing_url(item.get("id")),
    }


def save_csv(rows, path):
    if not rows:
        print("  [warn] no rows to write")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
    parser.add_argument("--detail", action="store_true",
                         help="Fetch the full detail record for every listing (slower, more fields).")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay in seconds between page requests.")
    args = parser.parse_args()

    session = make_session()

    print(f"Resolving make {args.make!r} ...")
    make_key, make_name = resolve_make_key(session, args.make, args.category)
    print(f"  -> make key={make_key!r} name={make_name!r}")

    print(f"Resolving model {args.model!r} for make {make_name!r} ...")
    model_key, model_name = resolve_model_key(session, make_key, args.model, args.category)
    print(f"  -> model key={model_key!r} name={model_name!r}")

    print(f"Fetching listings for {make_name} {model_name} (Switzerland, autoscout24.ch) ...")
    raw_listings = search_listings(session, make_key, model_key, args.category, delay=args.delay)

    if args.detail:
        print(f"Fetching full detail for {len(raw_listings)} listings ...")
        detailed = []
        for i, item in enumerate(raw_listings, 1):
            detail = fetch_detail(session, item["id"])
            # The detail endpoint only returns a bare sellerId, not the seller
            # name/city/zip/type that the search endpoint provides. Keep those.
            if "seller" in item:
                detail.setdefault("seller", item["seller"])
            detailed.append(detail)
            if i % 10 == 0 or i == len(raw_listings):
                print(f"  {i}/{len(raw_listings)}")
            time.sleep(args.delay)
        raw_listings = detailed

    rows = [flatten_listing(item) for item in raw_listings]
    rows.sort(key=lambda r: (r["price_chf"] is None, r["price_chf"]))

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
