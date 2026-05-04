from __future__ import annotations

import math
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.db.models import HotelCandidate, TripRequest


def google_api_error_detail(response: httpx.Response) -> str:
    """Human-readable snippet from Google Maps/Places JSON error (safe to log and show)."""
    try:
        data = response.json()
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                status = str(err.get("status") or "").strip()
                msg = str(err.get("message") or "").strip()
                if status or msg:
                    tail = f"{status}: {msg}".strip(": ").strip()
                    return tail[:500]
    except Exception:
        pass
    raw = (response.text or "").strip()
    return raw[:400] if raw else ""


# Statute miles → meters (Places API circle radius is in meters)
_MI_TO_M = 1609.344


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode_address(address: str, *, api_key: str) -> tuple[float, float] | None:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    r = httpx.get(url, params={"address": address, "key": api_key}, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        return None
    loc = results[0].get("geometry", {}).get("location", {})
    lat, lng = loc.get("lat"), loc.get("lng")
    if lat is None or lng is None:
        return None
    return float(lat), float(lng)


def search_lodging_places(
    text_query: str,
    *,
    api_key: str,
    max_results: int = 10,
    proximity_center: tuple[float, float] | None = None,
    radius_meters: float | None = None,
) -> list[dict[str, Any]]:
    """Places API (New) searchText.

    For Text Search, ``locationRestriction`` only allows a *rectangle*; a *circle* must
    use ``locationBias`` (see Places searchText reference). We bias with a circle, then
    apply a hard distance filter in ``build_hotels_for_trip``.
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(
            [
                "places.id",
                "places.displayName",
                "places.formattedAddress",
                "places.nationalPhoneNumber",
                "places.internationalPhoneNumber",
                "places.location",
                "places.rating",
                "places.googleMapsUri",
                "places.photos",
            ]
        ),
    }
    body: dict[str, Any] = {
        "textQuery": text_query,
        "maxResultCount": max_results,
    }
    if proximity_center is not None and radius_meters is not None and radius_meters > 0:
        lat, lng = proximity_center
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_meters),
            }
        }
    r = httpx.post(url, headers=headers, json=body, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    return list(data.get("places") or [])


def place_to_candidate(
    place: dict[str, Any],
    *,
    trip_id: uuid.UUID,
    ref_lat: float | None,
    ref_lng: float | None,
) -> HotelCandidate:
    pid = place.get("id") or ""
    name = (place.get("displayName") or {}).get("text") or "Hotel"
    addr = place.get("formattedAddress")
    phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
    if isinstance(phone, str) and phone and not phone.startswith("+"):
        phone = None

    loc = place.get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    rating = place.get("rating")

    meta: dict[str, Any] = {
        "google_place_id": pid,
        "rating": float(rating) if rating is not None else None,
        "maps_uri": place.get("googleMapsUri"),
    }
    photos = place.get("photos") or []
    if isinstance(photos, list) and photos:
        p0 = photos[0]
        if isinstance(p0, dict):
            pr = p0.get("name")
            if isinstance(pr, str) and pr.strip():
                meta["photo_resource_name"] = pr.strip()
    if lat is not None and lng is not None and ref_lat is not None and ref_lng is not None:
        meta["distance_km"] = round(_haversine_km(ref_lat, ref_lng, float(lat), float(lng)), 2)

    return HotelCandidate(
        trip_id=trip_id,
        place_id=(pid[:128] if pid else None),
        provider_ids={"google": pid},
        name=name[:256],
        address=addr[:512] if isinstance(addr, str) else None,
        phone_e164=phone[:32] if isinstance(phone, str) else None,
        extra_metadata=meta,
    )


def build_hotels_for_trip(trip: TripRequest, *, api_key: str) -> list[HotelCandidate]:
    """Geocode reference + destination, search lodging, return candidates."""
    ref_lat: float | None = None
    ref_lng: float | None = None
    ref_label = None
    if isinstance(trip.constraints, dict):
        ref_label = trip.constraints.get("reference_label")
        ref_lat = trip.constraints.get("reference_lat")
        ref_lng = trip.constraints.get("reference_lng")
    if trip.preferences and isinstance(trip.preferences, dict):
        ref_label = ref_label or trip.preferences.get("reference_location")

    if ref_lat is None and ref_lng is None and isinstance(ref_label, str) and ref_label.strip():
        geo = geocode_address(ref_label.strip(), api_key=api_key)
        if geo:
            ref_lat, ref_lng = geo

    dest_geo = geocode_address(trip.destination, api_key=api_key)
    q = f"hotels near {trip.destination}"
    if ref_label and str(ref_label).strip():
        q = f"hotels near {ref_label.strip()} {trip.destination}"

    radius_mi = float(settings.hotel_search_radius_miles)
    radius_m = max(radius_mi, 0.1) * _MI_TO_M
    radius_km = radius_mi * 1.609344

    anchor: tuple[float, float] | None = None
    if ref_lat is not None and ref_lng is not None:
        anchor = (float(ref_lat), float(ref_lng))
    elif dest_geo is not None:
        anchor = (dest_geo[0], dest_geo[1])

    places = search_lodging_places(
        q,
        api_key=api_key,
        max_results=max(4, int(settings.hotel_search_max_results) * 3),
        proximity_center=anchor,
        radius_meters=radius_m if anchor is not None else None,
    )
    out: list[HotelCandidate] = []
    seen: set[str] = set()
    for p in places:
        pid = p.get("id")
        if isinstance(pid, str) and pid in seen:
            continue
        if anchor is not None:
            loc = p.get("location") or {}
            pla, pln = loc.get("latitude"), loc.get("longitude")
            if pla is None or pln is None:
                continue
            d_km = _haversine_km(anchor[0], anchor[1], float(pla), float(pln))
            if d_km > radius_km + 0.25:
                continue
        if isinstance(pid, str):
            seen.add(pid)
        cand = place_to_candidate(p, trip_id=trip.id, ref_lat=ref_lat, ref_lng=ref_lng)
        # Secondary distance from destination center if no reference
        if "distance_km" not in cand.extra_metadata and dest_geo:
            loc = (p.get("location") or {})
            lat, lng = loc.get("latitude"), loc.get("longitude")
            if lat is not None and lng is not None:
                cand.extra_metadata["distance_km"] = round(
                    _haversine_km(dest_geo[0], dest_geo[1], float(lat), float(lng)), 2
                )
        out.append(cand)
    cap = max(1, int(settings.hotel_search_max_results))
    return out[:cap]


def google_hotels_enabled() -> bool:
    return bool(settings.google_maps_api_key) and settings.hotel_discovery_provider == "google"
