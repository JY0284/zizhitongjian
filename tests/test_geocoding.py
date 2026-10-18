import math

from scripts import geocode_locations_amap as geocoder
from scripts.merge_geocoding_into_unified_kb import merge_geocoding


def test_one_modern_city_match_is_not_a_verified_ancient_site(monkeypatch):
    monkeypatch.setattr(geocoder, "_amap_geocode_once", lambda **_: {
        "status": "1", "info": "OK", "infocode": "10000", "geocodes": [{
            "location": "114.49,36.61", "formatted_address": "河北省邯郸市", "level": "市"}]
    })
    result = geocoder.amap_geocode(["河北省邯郸市"], "test")
    assert result.coordinates_wgs84 is None
    assert result.needs_review
    assert result.candidate_coordinates_wgs84 is not None
    assert result.matched_address == "河北省邯郸市"
    assert result.match_level == "市"


def test_review_pending_clears_stale_coordinates_and_manual_override_wins():
    kb = {"locations": {"邯郸": {"coordinates": [114, 36]}}}
    geo = {"locations": {"邯郸": {"coordinates": [115, 37], "needs_review": True}}}
    merge_geocoding(kb, geo)
    assert kb["locations"]["邯郸"]["coordinates"] is None
    geo["overrides"] = {"邯郸": {"coordinates": [114.49, 36.61], "notes": "Reviewed source"}}
    merge_geocoding(kb, geo)
    assert kb["locations"]["邯郸"]["coordinates"] == [114.49, 36.61]
    assert kb["locations"]["邯郸"]["geocoding"]["source"] == "override"


def test_invalid_coordinates_are_never_merged():
    for coords in ([math.nan, 36], [114, math.inf], [181, 36], [114, 91]):
        assert not geocoder._coords_ok(coords)
        kb = {"locations": {"邯郸": {"coordinates": None}}}
        merge_geocoding(kb, {"locations": {"邯郸": {"coordinates": coords, "needs_review": False}}})
        assert kb["locations"]["邯郸"]["coordinates"] is None
