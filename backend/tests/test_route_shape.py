"""SB-394: route identity from track shape — fingerprinting + two-level clustering."""

from __future__ import annotations

from src.shared.route_shape import (
    cluster,
    families_and_variants,
    fingerprint,
    similarity,
)

# A block near the owner's home cell. Coordinates are arbitrary but realistic in
# scale: 0.01 deg latitude is ~1.1 km, so these are street-sized legs.
HOME = (42.2440, -71.6510)


def _leg(
    start: tuple[float, float], dlat: float, dlon: float, steps: int = 4
) -> list[tuple[float, float]]:
    lat, lon = start
    return [(lat + dlat * i / steps, lon + dlon * i / steps) for i in range(steps + 1)]


def _loop(dlat: float, dlon: float) -> list[tuple[float, float]]:
    """Rectangular loop out of HOME and back."""
    a = _leg(HOME, dlat, 0.0)
    b = _leg(a[-1], 0.0, dlon)
    c = _leg(b[-1], -dlat, 0.0)
    d = _leg(c[-1], 0.0, -dlon)
    return a + b + c + d


def test_fingerprint_fills_gaps_between_sparse_points() -> None:
    """Simplified polylines are sparse; the fingerprint must cover the path."""
    sparse = [HOME, (HOME[0] + 0.01, HOME[1])]  # ~1.1 km in two points
    fp = fingerprint(sparse)
    # ~1.1 km of 150 m cells -> several cells, not just the two endpoints.
    assert len(fp) > 5


def test_identical_tracks_match_exactly() -> None:
    fp = fingerprint(_loop(0.006, 0.006))
    assert similarity(fp, fp) == 1.0


def test_reverse_direction_is_the_same_route() -> None:
    """Cell sets have no direction, so a loop run backwards matches."""
    forward = _loop(0.006, 0.006)
    fp_a = fingerprint(forward)
    fp_b = fingerprint(list(reversed(forward)))
    assert similarity(fp_a, fp_b) > 0.95


def test_disjoint_tracks_do_not_match() -> None:
    home = fingerprint(_loop(0.006, 0.006))
    away = fingerprint(_leg((41.8934, -87.6244), 0.01, 0.01, steps=20))
    assert similarity(home, away) == 0.0


def test_empty_fingerprint_never_matches() -> None:
    assert similarity(frozenset(), fingerprint(_loop(0.006, 0.006))) == 0.0
    assert fingerprint([]) == frozenset()
    assert fingerprint([HOME]) == frozenset()


def test_cluster_is_single_link_not_first_match() -> None:
    """A bridging run chains both neighbours into one cluster, order-independently."""
    a = frozenset({(0, 0), (0, 1), (0, 2), (0, 3)})
    c = frozenset({(0, 2), (0, 3), (0, 4), (0, 5)})
    bridge = frozenset({(0, 1), (0, 2), (0, 3), (0, 4)})
    # a<->c overlap is only 2/6; each overlaps the bridge 3/5.
    assert similarity(a, c) < 0.5
    assert similarity(a, bridge) >= 0.5

    assert cluster([a, bridge, c], threshold=0.5) == [[0, 1, 2]]
    # Same answer whatever order they arrive in.
    assert cluster([c, a, bridge], threshold=0.5) == [[0, 1, 2]]


def test_variants_nest_inside_one_family() -> None:
    """Slight variations = one family, several variants (the owner's 3-4 routes)."""
    base = _loop(0.006, 0.006)
    # Same loop plus a short out-and-back on a street the loop doesn't use —
    # mostly shared path, but genuinely different ground for a stretch.
    variation = base + _leg(base[-1], 0.0, -0.003)
    tracks = [base, base, variation, variation, variation]
    fps = [fingerprint(t) for t in tracks]

    fams = families_and_variants(fps, family_overlap=0.4, variant_overlap=0.95)
    assert len(fams) == 1  # one family
    assert len(fams[0]) == 2  # two variants inside it
    assert sorted(len(v) for v in fams[0]) == [2, 3]
    # Counts add up: every run lands in exactly one variant of one family.
    assert sum(len(v) for v in fams[0]) == len(tracks)


def test_genuinely_different_routes_are_separate_families() -> None:
    """Same start, same length, different streets -> two families, not one."""
    north = _loop(0.006, 0.006)
    south = _loop(-0.006, -0.006)
    fps = [fingerprint(north), fingerprint(north), fingerprint(south), fingerprint(south)]

    fams = families_and_variants(fps)
    assert len(fams) == 2
    assert sorted(sum(len(v) for v in f) for f in fams) == [2, 2]


def test_untracked_runs_become_their_own_families() -> None:
    """No polyline -> can't match anything, but must not vanish from the board."""
    real = fingerprint(_loop(0.006, 0.006))
    fams = families_and_variants([real, real, frozenset(), frozenset()])
    sizes = sorted(sum(len(v) for v in f) for f in fams)
    assert sizes == [1, 1, 2]  # the pair matched; the two empties stand alone
