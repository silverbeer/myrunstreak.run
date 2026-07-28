"""Route identity from GPS track shape (SB-394).

The old identity — rounded start cell + distance bucket — cannot separate two
routes that leave the same house and run the same distance, which is most of a
home-based runner's history. This module identifies a route by the *path* the
run traces.

A track is fingerprinted as the set of grid cells its path passes through, and
two runs are "the same" when their cell sets overlap enough (Jaccard). Sets have
no direction, so running a loop backwards matches for free, and a detour only
costs similarity in proportion to its length.

Clustering is two-level so one number doesn't have to answer two questions:

* **family** — loose overlap: "my 5.5 from home", counting slight variations
  together (the streak-flavoured number).
* **variant** — strict overlap *within* a family: the specific version.

Single-link at both levels, so variants always nest inside their family and the
counts add up.
"""

from __future__ import annotations

import math

# ~150 m at mid latitudes. Longitude is aspect-corrected by cos(lat) so cells
# stay roughly square wherever the runs are.
DEFAULT_CELL_DEG = 0.0015
# A run's grid cells must cover this fraction of the union to count as the same
# family / variant.
#
# Swept over the 403 prod tracks available at the time of writing: the pairwise
# similarity distribution is bimodal — a heavy mass at >= 0.8 (the same route on
# a different day) and a long spread below 0.6 (different routes), with the
# trough at 0.4-0.5. Family sits in the trough; variant sits inside the dense
# mass. Provisional — the sample is the oldest ~10% of history (backfill runs
# oldest-first), so re-sweep once SB-310 drains.
FAMILY_OVERLAP = 0.5
VARIANT_OVERLAP = 0.8
# Pairwise clustering is O(n^2); above this a group falls back to the coarse key
# rather than burning seconds on a request. No real route hits this.
MAX_CLUSTER_MEMBERS = 2000

Cell = tuple[int, int]
Fingerprint = frozenset[Cell]


def fingerprint(
    points: list[tuple[float, float]], cell_deg: float = DEFAULT_CELL_DEG
) -> Fingerprint:
    """The set of grid cells a track passes through.

    Points come from a Douglas-Peucker-simplified polyline, so a straight
    kilometre may be only two points — we walk each segment in sub-cell steps
    rather than sampling the vertices, or the fingerprint would be full of holes
    exactly where two routes run together.
    """
    if len(points) < 2:
        return frozenset()

    # Aspect-correct longitude once per track; a run doesn't span enough
    # latitude for the factor to drift.
    mean_lat = sum(p[0] for p in points) / len(points)
    lon_scale = max(math.cos(math.radians(mean_lat)), 0.01)

    cells: set[Cell] = set()
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:], strict=False):
        dlat = lat2 - lat1
        dlon = (lon2 - lon1) * lon_scale
        span = math.hypot(dlat, dlon)
        steps = max(1, int(span / (cell_deg / 2)))
        for i in range(steps + 1):
            t = i / steps
            cells.add(
                (
                    int(round((lat1 + dlat * t) / cell_deg)),
                    int(round((lon1 * lon_scale + dlon * t) / cell_deg)),
                )
            )
    return frozenset(cells)


def similarity(a: Fingerprint, b: Fingerprint) -> float:
    """Jaccard overlap of two fingerprints (0.0 - 1.0)."""
    if not a or not b:
        return 0.0
    shared = len(a & b)
    return shared / (len(a) + len(b) - shared)


def cluster(fingerprints: list[Fingerprint], threshold: float) -> list[list[int]]:
    """Single-link clusters of indices whose fingerprints overlap >= threshold.

    Single-link (union-find over every qualifying pair) rather than
    first-match-wins: a run that resembles two others chains them into one
    cluster instead of landing in whichever was checked first, which would make
    the result depend on input order.
    """
    n = len(fingerprints)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    for i in range(n):
        for j in range(i + 1, n):
            if similarity(fingerprints[i], fingerprints[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    # Deterministic order: by first member, so callers get stable output.
    return [groups[k] for k in sorted(groups)]


def families_and_variants(
    fingerprints: list[Fingerprint],
    family_overlap: float = FAMILY_OVERLAP,
    variant_overlap: float = VARIANT_OVERLAP,
) -> list[list[list[int]]]:
    """Two-level clustering: families, each split into variants.

    Returns one entry per family, each a list of variants, each a list of
    indices into ``fingerprints``. Every index appears exactly once, so family
    size is the sum of its variant sizes.

    Runs with an empty fingerprint (no usable track) each become their own
    single-member family — they can't be matched to anything, and dropping them
    would silently lose runs from the leaderboard.
    """
    families: list[list[list[int]]] = []
    for fam in cluster(fingerprints, family_overlap):
        if len(fam) == 1:
            families.append([fam])
            continue
        sub = cluster([fingerprints[i] for i in fam], variant_overlap)
        families.append([[fam[i] for i in variant] for variant in sub])
    return families
