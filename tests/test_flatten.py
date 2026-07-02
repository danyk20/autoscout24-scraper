"""Unit tests for _scalarize(), flatten_listing() and order_fieldnames()."""
import json

import autoscout24_scraper as scraper


# --- _scalarize -------------------------------------------------------

def test_scalarize_none_becomes_empty_string():
    assert scraper._scalarize(None) == ""


def test_scalarize_passthrough_scalars():
    assert scraper._scalarize("hello") == "hello"
    assert scraper._scalarize(42) == 42
    assert scraper._scalarize(3.14) == 3.14
    assert scraper._scalarize(True) is True
    assert scraper._scalarize(False) is False


def test_scalarize_dict_with_name_key():
    assert scraper._scalarize({"name": "TESLA", "key": "tesla"}) == "TESLA"


def test_scalarize_dict_with_feature_key():
    assert scraper._scalarize({"feature": "top-list"}) == "top-list"


def test_scalarize_dict_with_provider_name_key():
    assert scraper._scalarize({"providerName": "FinanceScout24", "url": "https://x"}) == "FinanceScout24"


def test_scalarize_dict_without_known_key_falls_back_to_json():
    value = {"height": None, "length": 100, "volume": None, "width": None}
    result = scraper._scalarize(value)
    assert json.loads(result) == value


def test_scalarize_list_of_scalars_joined_with_semicolons():
    assert scraper._scalarize(["a", "b", "c"]) == "a; b; c"


def test_scalarize_list_of_dicts_extracts_known_key_per_item():
    value = [{"feature": "top-list"}, {"feature": "premium"}]
    assert scraper._scalarize(value) == "top-list; premium"


def test_scalarize_nested_list_of_unrecognized_dicts_falls_back_to_json_per_item():
    value = [{"a": 1}, {"b": 2}]
    result = scraper._scalarize(value)
    parts = result.split("; ")
    assert json.loads(parts[0]) == {"a": 1}
    assert json.loads(parts[1]) == {"b": 2}


def test_scalarize_empty_list_is_empty_string():
    assert scraper._scalarize([]) == ""


def test_scalarize_unrecognized_type_falls_back_to_str():
    class Weird:
        def __str__(self):
            return "weird-value"

    assert scraper._scalarize(Weird()) == "weird-value"


# --- flatten_listing ----------------------------------------------------

def test_flatten_listing_extracts_seller_fields(summary_listing_factory):
    item = summary_listing_factory(1)
    flat = scraper.flatten_listing(item)

    assert flat["sellerName"] == "EGEN"
    assert flat["sellerType"] == "private"
    assert flat["sellerCity"] == "Yverdon-les-Bains"
    assert flat["sellerZip"] == "1400"
    assert "seller" not in flat


def test_flatten_listing_extracts_make_and_model_with_key(summary_listing_factory):
    item = summary_listing_factory(1)
    flat = scraper.flatten_listing(item)

    assert flat["make"] == "TESLA"
    assert flat["makeKey"] == "tesla"
    assert flat["model"] == "MODEL S"
    assert flat["modelKey"] == "model-s"


def test_flatten_listing_flattens_nested_dicts_with_prefix(summary_listing_factory):
    item = summary_listing_factory(1)
    flat = scraper.flatten_listing(item)

    assert flat["financing_providerName"] == "FinanceScout24"
    assert flat["financing_url"].startswith("https://kredit.financescout24.ch")
    assert flat["warranty_type"] == "none"


def test_flatten_listing_adds_constructed_url(summary_listing_factory):
    item = summary_listing_factory(999)
    flat = scraper.flatten_listing(item)

    assert flat["url"] == "https://www.autoscout24.ch/de/d/999"


def test_flatten_listing_scalar_fields_pass_through(summary_listing_factory):
    item = summary_listing_factory(1, price=12345.0, mileage=54321)
    flat = scraper.flatten_listing(item)

    assert flat["price"] == 12345.0
    assert flat["mileage"] == 54321
    assert flat["fuelType"] == "electric"
    assert flat["hadAccident"] is False


def test_flatten_listing_on_full_detail_shape_has_no_seller_object(detail_listing_factory):
    item = detail_listing_factory(1)
    flat = scraper.flatten_listing(item)

    # detail records only carry a bare sellerId, no nested "seller" dict
    assert flat["sellerId"] == 3001640
    assert "sellerName" not in flat
    assert flat["boot_height"] == ""
    assert flat["description"] == "A great car with a long description."


def test_flatten_listing_joins_images_list(summary_listing_factory):
    item = summary_listing_factory(1)
    flat = scraper.flatten_listing(item)

    assert "listing/1/1.jpeg" in flat["images"]
    assert "listing/1/2.jpeg" in flat["images"]
    assert "; " in flat["images"]


# --- order_fieldnames -----------------------------------------------------

def test_order_fieldnames_puts_priority_fields_first_in_declared_order():
    keys = {"zzz_extra", "price", "id", "aaa_extra", "make"}
    ordered = scraper.order_fieldnames(keys)

    priority_present = [f for f in scraper.PRIORITY_FIELDS if f in keys]
    assert ordered[: len(priority_present)] == priority_present


def test_order_fieldnames_sorts_remaining_fields_alphabetically():
    keys = {"id", "zzz_extra", "aaa_extra", "mmm_extra"}
    ordered = scraper.order_fieldnames(keys)

    remaining = [f for f in ordered if f not in scraper.PRIORITY_FIELDS]
    assert remaining == sorted(remaining)


def test_order_fieldnames_includes_every_key_exactly_once():
    keys = {"id", "price", "custom_field_a", "custom_field_b"}
    ordered = scraper.order_fieldnames(keys)

    assert set(ordered) == keys
    assert len(ordered) == len(keys)
