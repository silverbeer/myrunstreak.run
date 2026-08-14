"""Polyline simplification + encoding for stored GPS tracks (SB-309).

Turns a run's raw lat/lon arrays into a compact, storable string:
Douglas-Peucker simplification (drop points that don't change the line's shape)
then Google's Encoded Polyline Algorithm Format. ~578 raw points -> ~1-2 KB.
"""

from __future__ import annotations

import math

# One degree of latitude is ~111 km; used to turn a metre tolerance into the
# degree-space epsilon Douglas-Peucker works in.
_DEG_PER_M_LAT = 1.0 / 111_320.0


def _perp_distance(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """Perpendicular distance from point p to segment a-b, in degree units,
    aspect-corrected so longitude and latitude are comparable at this latitude."""
    k = math.cos(math.radians(a[0])) or 1e-9
    ax, ay = a[1] * k, a[0]
    bx, by = b[1] * k, b[0]
    px, py = p[1] * k, p[0]
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def douglas_peucker(
    points: list[tuple[float, float]], tolerance_m: float = 6.0
) -> list[tuple[float, float]]:
    """Simplify a (lat, lon) path, keeping points that matter to its shape.

    tolerance_m is the max deviation allowed (metres) — ~6 m is imperceptible on
    a route map and typically drops 50-70% of running-GPS points.
    """
    if len(points) < 3:
        return list(points)
    eps = tolerance_m * _DEG_PER_M_LAT

    # Iterative stack to avoid recursion limits on long tracks.
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        dmax, idx = 0.0, start
        for i in range(start + 1, end):
            d = _perp_distance(points[i], points[start], points[end])
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps and idx != start:
            keep[idx] = True
            stack.append((start, idx))
            stack.append((idx, end))
    return [p for p, k in zip(points, keep, strict=True) if k]


def _encode_signed(value: int) -> str:
    """Google polyline: zigzag + 5-bit-chunk base64-ish encoding of one number."""
    value = ~(value << 1) if value < 0 else (value << 1)
    out = []
    while value >= 0x20:
        out.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    out.append(chr(value + 63))
    return "".join(out)


def encode_polyline(points: list[tuple[float, float]], precision: int = 5) -> str:
    """Encode (lat, lon) points as a Google Encoded Polyline string.

    precision=5 -> ~1.1 m resolution, plenty for a running route.
    """
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lon = 0
    for lat, lon in points:
        ilat = round(lat * factor)
        ilon = round(lon * factor)
        out.append(_encode_signed(ilat - prev_lat))
        out.append(_encode_signed(ilon - prev_lon))
        prev_lat, prev_lon = ilat, ilon
    return "".join(out)


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Inverse of encode_polyline — for tests and client-side rendering."""
    factor = 10**precision
    points: list[tuple[float, float]] = []
    i = lat = lon = 0
    while i < len(encoded):
        for is_lon in (False, True):
            shift = result = 0
            while True:
                b = ord(encoded[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if is_lon:
                lon += delta
            else:
                lat += delta
        points.append((lat / factor, lon / factor))
    return points


def simplify_and_encode(
    lat: list[float], lon: list[float], tolerance_m: float = 6.0
) -> tuple[str, int]:
    """Raw lat/lon arrays -> (encoded simplified polyline, kept point count).

    Returns ("", 0) when there's nothing to store (no / degenerate track).
    """
    if not lat or len(lat) != len(lon) or len(lat) < 2:
        return "", 0
    pts = list(zip(lat, lon, strict=True))
    simplified = douglas_peucker(pts, tolerance_m)
    return encode_polyline(simplified), len(simplified)


_EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def path_length_km(points: list[tuple[float, float]]) -> float:
    """Total length of a (lat, lon) path in km.

    Used by file import (SB-99): GPX carries trackpoints but no distance field,
    so the run's distance has to come from the track itself. Summing raw
    consecutive fixes slightly over-reads distance because GPS noise adds
    length, which is why this is only a fallback for formats that state no
    distance of their own — TCX does, and that stated value wins.
    """
    return sum(haversine_km(points[i - 1], points[i]) for i in range(1, len(points)))
