"""SB-311: territory heatmap decodes polylines and renders (or empty-states)."""

from __future__ import annotations

from typing import Any

from cli import display
from rich.console import Console


def _render(data: dict[str, Any]) -> str:
    console = Console(record=True, width=100)
    original = display.console
    display.console = console
    try:
        display.display_territory_heatmap(data, w=30, h=12)
    finally:
        display.console = original
    return console.export_text()


def test_decode_polyline_matches_google_reference() -> None:
    # Inverse of the canonical Google encoding example.
    pts = display._decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert len(pts) == 3
    assert abs(pts[0][0] - 38.5) < 1e-4
    assert abs(pts[0][1] - -120.2) < 1e-4
    assert abs(pts[2][0] - 43.252) < 1e-4


def test_heatmap_empty_state_when_no_tracks() -> None:
    out = _render({"tracks": []})
    assert "No route data yet" in out


def test_heatmap_renders_legend_and_counts() -> None:
    # Two simple encoded routes -> a panel with the route/point legend.
    # "gfo}EtohhU..." style — use a short real encoding of a couple points each.
    routes = [
        {"polyline": display_encode([(42.0, -71.0), (42.01, -71.01), (42.02, -71.0)])},
        {"polyline": display_encode([(42.0, -71.0), (42.01, -71.01), (42.02, -71.0)])},
    ]
    out = _render({"tracks": routes})
    assert "Your territory" in out
    assert "2 routes" in out


def display_encode(pts: list[tuple[float, float]], precision: int = 5) -> str:
    """Local encoder mirroring the stk decoder, for building test fixtures."""
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lon = 0
    for lat, lon in pts:
        for value in (round(lat * factor) - prev_lat, round(lon * factor) - prev_lon):
            v = ~(value << 1) if value < 0 else (value << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        prev_lat, prev_lon = round(lat * factor), round(lon * factor)
    return "".join(out)
