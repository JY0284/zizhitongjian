#!/usr/bin/env python3
"""Geocode unified locations using Amap (Gaode) and maintain a persistent cache.

- Input: `data/unified_knowledge.json`
- Output: `data/location_geocoding.json`

Secrets:
- Reads API key from env var `AMAP_KEY`.

Notes:
- Amap geocoding returns GCJ-02 coordinates; this script converts to WGS84.
- Cache is append/update-only and preserves `overrides`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from tqdm import tqdm  # type: ignore
except Exception:  # pragma: no cover
    def tqdm(iterable, **kwargs):  # type: ignore
        return iterable


def _now_iso() -> str:
    return datetime.now().isoformat()


def _load_dotenv_if_present(dotenv_path: Path) -> None:
    """Minimal .env loader (no external dependency).

    Only supports simple `KEY=VALUE` lines. Ignores comments and blank lines.
    Does not override already-set environment variables.
    """

    if not dotenv_path.exists() or not dotenv_path.is_file():
        return
    try:
        text = dotenv_path.read_text(encoding="utf-8")
    except Exception:
        return

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue
        os.environ[key] = value


# --- GCJ-02 -> WGS84 conversion (approx.) ---

_PI = 3.1415926535897932384626
_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lng: float, lat: float) -> bool:
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * (abs(lng) ** 0.5)
    ret += (20.0 * __import__("math").sin(6.0 * lng * _PI) + 20.0 * __import__("math").sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * __import__("math").sin(lat * _PI) + 40.0 * __import__("math").sin(lat / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * __import__("math").sin(lat / 12.0 * _PI) + 320 * __import__("math").sin(lat * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * (abs(lng) ** 0.5)
    ret += (20.0 * __import__("math").sin(6.0 * lng * _PI) + 20.0 * __import__("math").sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * __import__("math").sin(lng * _PI) + 40.0 * __import__("math").sin(lng / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * __import__("math").sin(lng / 12.0 * _PI) + 300.0 * __import__("math").sin(lng / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    if _out_of_china(lng, lat):
        return lng, lat

    import math

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _PI
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * _PI)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * _PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


@dataclass
class GeocodeResult:
    provider: str
    query: str
    coordinates_wgs84: Optional[Tuple[float, float]]
    confidence: float
    needs_review: bool
    evidence: str
    infocode: Optional[str] = None
    info: Optional[str] = None
    candidate_coordinates_wgs84: Optional[Tuple[float, float]] = None
    candidate_count: Optional[int] = None
    matched_address: Optional[str] = None
    match_level: Optional[str] = None


class GeocodingProviderError(RuntimeError):
    """Safe diagnostics without the request URL, which contains a key."""


def _amap_geocode_once(address: str, api_key: str, timeout_sec: float = 20.0) -> Dict[str, Any]:
    params = {"address": address, "key": api_key}
    url = "https://restapi.amap.com/v3/geocode/geo?" + urlencode(params)

    req = Request(url, headers={"User-Agent": "zizhitongjian-geocoder/1.0"})
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError) as exc:
        raise GeocodingProviderError(type(exc).__name__) from None


def amap_geocode(address_candidates: list[str], api_key: str, timeout_sec: float = 20.0) -> GeocodeResult:
    last_info: Optional[str] = None
    last_infocode: Optional[str] = None

    for address in address_candidates:
        if not address:
            continue

        payload = _amap_geocode_once(address=address, api_key=api_key, timeout_sec=timeout_sec)

        info = payload.get("info")
        infocode = payload.get("infocode")
        if payload.get("status") != "1":
            code = str(infocode)
            raise GeocodingProviderError("Amap rejected request; infocode=" + (code if code.isdigit() else "unknown"))

        geocodes = payload.get("geocodes") or []
        if not geocodes:
            last_info = "no results"
            last_infocode = infocode
            continue

        # If multiple candidates, treat as ambiguous: do not output authoritative coordinates.
        if len(geocodes) != 1:
            loc_str = geocodes[0].get("location")
            cand: Optional[Tuple[float, float]] = None
            if loc_str and "," in loc_str:
                try:
                    lng_gcj, lat_gcj = (float(x) for x in loc_str.split(",", 1))
                    cand = gcj02_to_wgs84(lng_gcj, lat_gcj)
                except Exception:
                    cand = None

            return GeocodeResult(
                provider="amap",
                query=address,
                coordinates_wgs84=None,
                confidence=0.0,
                needs_review=True,
                evidence=f"amap ambiguous: {len(geocodes)} candidates",
                infocode=infocode,
                info=info,
                candidate_coordinates_wgs84=cand,
                candidate_count=len(geocodes),
            )

        # Amap returns GCJ-02 coordinates: "lng,lat"
        loc_str = geocodes[0].get("location")
        if not loc_str or "," not in loc_str:
            last_info = "missing location field"
            last_infocode = infocode
            continue

        lng_gcj, lat_gcj = (float(x) for x in loc_str.split(",", 1))
        lng_wgs, lat_wgs = gcj02_to_wgs84(lng_gcj, lat_gcj)

        match = geocodes[0]
        # A modern address match alone does not establish an ancient site's location.
        return GeocodeResult(
            provider="amap",
            query=address,
            coordinates_wgs84=None,
            confidence=0.6,
            needs_review=True,
            evidence="Modern address candidate; historical identification requires review",
            infocode=infocode,
            info=info,
            candidate_coordinates_wgs84=(lng_wgs, lat_wgs),
            candidate_count=1,
            matched_address=match.get("formatted_address"),
            match_level=match.get("level"),
        )

    return GeocodeResult(
        provider="amap",
        query=(address_candidates[0] if address_candidates else ""),
        coordinates_wgs84=None,
        confidence=0.0,
        needs_review=True,
        evidence=f"amap failed: {last_info or 'unknown'}",
        infocode=last_infocode,
        info=last_info,
    )


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _coords_ok(coords: Any) -> bool:
    if coords is None:
        return False
    if not isinstance(coords, (list, tuple)) or len(coords) != 2:
        return False
    try:
        lng, lat = float(coords[0]), float(coords[1])
    except Exception:
        return False
    return math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180 and -90 <= lat <= 90


def _clean_query(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""

    # Drop low-signal phrases that frequently trigger engine errors.
    for bad in ["不详", "待考", "具体位置", "有争议", "已湮没", "并入其他水系", "附近", "一带", "等地", "或", "一说"]:
        if bad in s:
            s = s.split(bad, 1)[0].strip()

    # Prefer the first clause.
    for sep in ["、", "，", ",", "；", ";", "（", "("]:
        if sep in s:
            s = s.split(sep, 1)[0].strip()

    # Avoid extremely long queries.
    if len(s) > 30:
        s = s[:30].strip()

    return s


def build_query_candidates(loc_id: str, canonical_name: str, modern_name: str, location_type: str) -> list[str]:
    candidates: list[str] = []

    modern_clean = _clean_query(modern_name)
    canonical_clean = _clean_query(canonical_name) or _clean_query(loc_id)

    if modern_clean:
        candidates.append(modern_clean)
    if canonical_clean and canonical_clean not in candidates:
        candidates.append(canonical_clean)

    # For single-character polities like 周/楚/燕, add disambiguation.
    if location_type == "国家" and canonical_clean and len(canonical_clean) == 1:
        for suffix in ["国", "古国", "古代"]:
            q = canonical_clean + suffix
            if q not in candidates:
                candidates.append(q)

    # Some conceptual locations shouldn't be geocoded; still keep minimal fallback.
    return [c for c in candidates if c]


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Geocode unified locations with Amap and update a local cache")
    parser.add_argument("--kb", default="data/unified_knowledge.json", help="Path to unified KB JSON")
    parser.add_argument("--out", default="data/location_geocoding.json", help="Path to geocoding cache JSON")
    parser.add_argument("--sleep", type=float, default=0.25, help="Sleep seconds between requests")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of locations to process (0 = no limit)")
    parser.add_argument("--refresh", action="store_true", help="Re-geocode even if cache entry already exists")
    parser.add_argument(
        "--simulate",
        "--dry-run",
        dest="simulate",
        action="store_true",
        help=(
            "Do not call Amap; only write queries + needs_review. "
            "(Use --simulate with `uv run` to avoid option conflicts.)"
        ),
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
        help="Write cache to disk every N updates (0 = only at the end)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help="Max Amap attempts per location when coordinates remain null (default 1)",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry locations that previously attempted Amap but still have null coordinates",
    )
    args = parser.parse_args()

    kb_path = Path(args.kb)
    out_path = Path(args.out)

    kb = load_json(kb_path)
    locations = kb.get("locations") or {}

    cache = load_json(out_path)
    cache.setdefault("version", "v1")
    cache.setdefault("provider", "amap")
    cache.setdefault("generated_at", _now_iso())
    cache.setdefault("locations", {})
    cache.setdefault("overrides", {})

    overrides = cache.get("overrides") or {}

    _load_dotenv_if_present(Path(".env"))
    api_key = os.getenv("AMAP_KEY")
    if not api_key:
        # Auto-switch to simulate if no key
        args.simulate = True

    # Preflight: compute how many items need processing
    total_locations = len(locations)
    overrides_with_coords = sum(1 for v in overrides.values() if _coords_ok((v or {}).get("coordinates")))
    cache_locations = cache.get("locations") or {}
    cache_entries = len(cache_locations)
    cache_with_coords = sum(1 for v in cache_locations.values() if _coords_ok((v or {}).get("coordinates")))

    def _attempts(entry: Dict[str, Any]) -> int:
        if "attempts" in entry:
            try:
                return int(entry.get("attempts") or 0)
            except Exception:
                return 0
        # Backward-compat: older cache entries didn't record attempts.
        # If Amap was called and still no coordinates, treat as 1 attempt.
        if entry.get("source") == "amap" and not _coords_ok(entry.get("coordinates")):
            return 1
        return 0

    def _needs_geocoding(loc_id: str) -> bool:
        if _coords_ok((overrides.get(loc_id) or {}).get("coordinates")):
            existing = cache_locations.get(loc_id) or {}
            return (existing.get("coordinates") != overrides[loc_id]["coordinates"]
                    or existing.get("source") != "override")
        if args.refresh:
            return True
        existing = cache_locations.get(loc_id) or {}
        if _coords_ok(existing.get("coordinates")):
            return False

        # Don't endlessly retry Amap failures by default.
        already_attempted = (existing.get("source") == "amap") and (_attempts(existing) >= max(1, int(args.max_attempts)))
        if already_attempted and not args.retry_failed:
            return False

        return True

    candidates = sorted(
        ((loc_id, loc) for loc_id, loc in locations.items() if _needs_geocoding(loc_id)),
        key=lambda x: x[0],
    )
    candidates_total = len(candidates)
    candidates_to_run = candidates
    if args.limit and args.limit > 0:
        candidates_to_run = candidates[: args.limit]

    print(
        "Geocoding preflight: "
        + json.dumps(
            {
                "total_unified_locations": total_locations,
                "overrides_with_coords": overrides_with_coords,
                "cache_entries": cache_entries,
                "cache_with_coords": cache_with_coords,
                "needs_geocoding_total": candidates_total,
                "will_process_now": len(candidates_to_run),
                "refresh": bool(args.refresh),
                "simulate": bool(args.simulate),
                "checkpoint_every": int(args.checkpoint_every),
                "max_attempts": int(args.max_attempts),
                "retry_failed": bool(args.retry_failed),
            },
            ensure_ascii=False,
        )
    )
    if candidates_total == 0:
        print("Nothing to do.")
        return 0

    processed = 0
    updated = 0
    updated_since_checkpoint = 0

    iterator = tqdm(
        candidates_to_run,
        total=len(candidates_to_run),
        desc="Geocoding",
        unit="loc",
        disable=not sys.stderr.isatty(),
    )

    for loc_id, loc in iterator:
        processed += 1

        canonical_name = loc.get("canonical_name") or loc_id
        modern_name = loc.get("modern_name") or ""
        location_type = loc.get("location_type") or ""
        query_candidates = build_query_candidates(
            loc_id=loc_id,
            canonical_name=str(canonical_name),
            modern_name=str(modern_name),
            location_type=str(location_type),
        )
        query = query_candidates[0] if query_candidates else (str(canonical_name).strip() or loc_id)

        if _coords_ok((overrides.get(loc_id) or {}).get("coordinates")):
            coords = overrides[loc_id]["coordinates"]
            cache["locations"][loc_id] = {
                "location_id": loc_id,
                "canonical_name": canonical_name,
                "modern_name": modern_name,
                "query": query,
                "coordinates": coords,
                "confidence": 1.0,
                "source": "override",
                "evidence": overrides[loc_id].get("notes", "manual override"),
                "needs_review": False,
                "updated_at": _now_iso(),
            }
            updated += 1
            updated_since_checkpoint += 1
            if args.checkpoint_every > 0 and updated_since_checkpoint >= args.checkpoint_every:
                cache["generated_at"] = _now_iso()
                save_json(out_path, cache)
                updated_since_checkpoint = 0
            continue

        # Note: non-refresh skipping is already handled by candidate filtering.

        if args.simulate:
            cache["locations"][loc_id] = {
                "location_id": loc_id,
                "canonical_name": canonical_name,
                "modern_name": modern_name,
                "query": query,
                "coordinates": None,
                "confidence": 0.0,
                "source": "dry-run",
                "evidence": "simulate mode (no API call)",
                "needs_review": True,
                "updated_at": _now_iso(),
            }
            updated += 1
            updated_since_checkpoint += 1
            if args.checkpoint_every > 0 and updated_since_checkpoint >= args.checkpoint_every:
                cache["generated_at"] = _now_iso()
                save_json(out_path, cache)
                updated_since_checkpoint = 0
            continue

        prev = cache_locations.get(loc_id) or {}
        prev_attempts = _attempts(prev)

        try:
            result = amap_geocode(query_candidates or [query], api_key=api_key)
        except GeocodingProviderError as exc:
            save_json(out_path, cache)
            print(f"Stopped geocoding: {exc}; completed results retained in {out_path}", file=sys.stderr)
            return 1
        coords = list(result.coordinates_wgs84) if result.coordinates_wgs84 else None
        candidate_coords = (
            list(result.candidate_coordinates_wgs84)
            if result.candidate_coordinates_wgs84 is not None
            else None
        )
        cache["locations"][loc_id] = {
            "location_id": loc_id,
            "canonical_name": canonical_name,
            "modern_name": modern_name,
            "query": result.query,
            "modern_reference": bool(modern_name) and result.query == _clean_query(str(modern_name)),
            # Only set authoritative coordinates when confident.
            "coordinates": coords if (coords is not None and not result.needs_review) else None,
            "candidate_coordinates": candidate_coords,
            "candidate_count": result.candidate_count,
            "matched_address": result.matched_address,
            "match_level": result.match_level,
            "confidence": result.confidence,
            "source": result.provider,
            "evidence": result.evidence,
            "info": result.info,
            "infocode": result.infocode,
            "needs_review": result.needs_review,
            "attempts": prev_attempts + 1,
            "updated_at": _now_iso(),
        }
        updated += 1
        updated_since_checkpoint += 1
        if args.checkpoint_every > 0 and updated_since_checkpoint >= args.checkpoint_every:
            cache["generated_at"] = _now_iso()
            save_json(out_path, cache)
            updated_since_checkpoint = 0
        time.sleep(max(0.0, float(args.sleep)))

    cache["generated_at"] = _now_iso()
    save_json(out_path, cache)

    print(f"Wrote {out_path} (processed={processed}, updated={updated}, simulate={args.simulate})")
    if args.simulate:
        print("Tip: set AMAP_KEY (and omit --simulate) to enable real geocoding")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
