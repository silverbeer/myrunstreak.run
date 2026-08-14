"""Shared XML helpers for the GPX/TCX parsers (SB-99).

Parsing is done with ``defusedxml``: these files are user uploads, and
``xml.etree`` is documented as vulnerable to entity-expansion ("billion
laughs") and quadratic-blowup attacks. A size cap alone does not help — a few
hundred bytes of nested entities is enough to exhaust memory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import ParseError, fromstring

from .errors import ActivityParseError


def parse_xml(content: bytes) -> Element:
    """Safely parse XML bytes into an element tree root."""
    try:
        root: Element = fromstring(content)
    except ParseError as exc:
        raise ActivityParseError(f"File is not valid XML: {exc}") from exc
    return root


def local_name(tag: str) -> str:
    """``{http://ns}trkpt`` -> ``trkpt``.

    GPX and TCX both namespace every element, and the namespace URI varies by
    the app that wrote the file (and by schema version). Matching on the local
    name keeps the parsers working across writers instead of hard-coding one
    vendor's URI.
    """
    return tag.rsplit("}", 1)[-1]


def find_all(element: Element, name: str) -> list[Element]:
    """Every descendant whose local name matches, namespace ignored."""
    return [el for el in element.iter() if local_name(el.tag) == name]


def find_first(element: Element, name: str) -> Element | None:
    for el in element.iter():
        if local_name(el.tag) == name:
            return el
    return None


def child_text(element: Element, name: str) -> str | None:
    """Text of the first *direct or nested* child with this local name."""
    found = find_first(element, name)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def child_float(element: Element, name: str) -> float | None:
    raw = child_text(element, name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_timestamp(raw: str | None) -> datetime | None:
    """ISO-8601 timestamp as written by GPX/TCX (``...Z`` or with an offset)."""
    if not raw:
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # A file that states no offset is UTC by both specs.
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
