"""SB-309: polyline simplify + encode round-trips and stays accurate."""

from __future__ import annotations

import math

from src.shared.geo import (
    decode_polyline,
    douglas_peucker,
    encode_polyline,
    simplify_and_encode,
)


def test_encode_decode_roundtrip_within_precision() -> None:
    pts = [(42.24431, -71.65018), (42.25011, -71.64998), (42.24399, -71.65044)]
    back = decode_polyline(encode_polyline(pts))
    assert len(back) == len(pts)
    for (la, lo), (ba, bo) in zip(pts, back, strict=True):
        assert abs(la - ba) < 1e-5
        assert abs(lo - bo) < 1e-5


def test_encode_matches_google_reference() -> None:
    # The canonical example from Google's polyline algorithm docs.
    pts = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    assert encode_polyline(pts) == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


def test_douglas_peucker_drops_collinear_points() -> None:
    # A straight line of 5 points collapses to its 2 endpoints.
    line = [(42.0, -71.0), (42.1, -71.0), (42.2, -71.0), (42.3, -71.0), (42.4, -71.0)]
    simplified = douglas_peucker(line, tolerance_m=6.0)
    assert simplified == [(42.0, -71.0), (42.4, -71.0)]


def test_douglas_peucker_keeps_a_real_corner() -> None:
    # An L-shape must keep the corner point.
    path = [(42.0, -71.0), (42.0, -71.01), (42.0, -71.02), (42.01, -71.02), (42.02, -71.02)]
    simplified = douglas_peucker(path, tolerance_m=6.0)
    assert (42.0, -71.02) in simplified  # the corner survives
    assert len(simplified) < len(path)


def test_simplify_reduces_a_noisy_track_but_stays_faithful() -> None:
    # A realistic ~1 km circular loop sampled densely (points along a smooth
    # arc) — simplification should shrink it while keeping the endpoints.
    r = 0.0045  # ~500 m radius in degrees
    lat = [42.0 + r * math.sin(2 * math.pi * i / 120) for i in range(120)]
    lon = [-71.0 + r * math.cos(2 * math.pi * i / 120) for i in range(120)]
    encoded, n = simplify_and_encode(lat, lon, tolerance_m=6.0)
    assert 2 <= n < len(lat)  # actually reduced
    decoded = decode_polyline(encoded)
    assert len(decoded) == n
    # Endpoints preserved exactly (to precision).
    assert abs(decoded[0][0] - lat[0]) < 1e-4
    assert abs(decoded[-1][0] - lat[-1]) < 1e-4


def test_simplify_and_encode_handles_empty_and_degenerate() -> None:
    assert simplify_and_encode([], []) == ("", 0)
    assert simplify_and_encode([42.0], [-71.0]) == ("", 0)
    assert simplify_and_encode([42.0, 42.1], [-71.0]) == ("", 0)  # mismatched


def test_two_point_track_encodes_without_simplifying() -> None:
    encoded, n = simplify_and_encode([42.0, 42.1], [-71.0, -71.1])
    assert n == 2
    assert math.isclose(decode_polyline(encoded)[1][0], 42.1, abs_tol=1e-4)
