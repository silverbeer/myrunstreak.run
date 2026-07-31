"""Name matching for the exercise catalog: search and duplicate detection (SB-454).

The catalog's dedup strategy is deliberately soft — no unique-on-name constraint,
because real variants ("push-up" and "incline push-up") must coexist. What holds
it together instead is:

  1. search-first selection, so a coach finds the existing row before adding one, and
  2. a duplicate guard on create/publish that returns candidates rather than
     silently inserting a second row.

Both need the same notion of "the same name", which is what ``normalize`` provides.
``scripts/audit_exercise_catalog.py`` imports it too, so the offline audit can never
drift from what the running service actually does.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "find_duplicate_candidates",
    "matches_query",
    "normalize",
    "search_terms",
    "squash",
]


def normalize(name: str) -> str:
    """Fold the spellings a coach might use into one comparable form.

    Lowercases, turns hyphens/underscores/punctuation into spaces, collapses
    whitespace, and drops a trailing plural ``s`` from each token. ``"Bent-over
    row"``, ``"bent over rows"`` and ``"BENT OVER ROW"`` all become
    ``"bent over row"``.

    ``ss`` endings keep their ``s`` so "press" doesn't become "pres". Plural
    stripping is otherwise unconditional: it is not trying to be linguistically
    correct, only *consistent*. Both sides of every comparison run through this
    function, so an over-eager fold like "abs" → "ab" costs nothing, while a
    conservative one leaves "ups" and "up" as different words.

    Apostrophes are *deleted* rather than turned into a space: "Farmer's carry"
    has to fold onto the "farmers carry" a coach types, and splitting on the
    apostrophe would instead leave a stray "s" token that matches neither.
    """
    text = name.lower().replace("-", " ").replace("_", " ")
    text = re.sub(r"['‘’ʼ]", "", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [
        token[:-1] if len(token) > 1 and token.endswith("s") and not token.endswith("ss") else token
        for token in text.split()
    ]
    return " ".join(tokens)


def squash(name: str) -> str:
    """Normalized with the word breaks removed: "Push-ups" -> "pushup".

    Catches the coach who types the name as one word. "pushups", "warmup" and
    "stepup" are at least as likely as the spaced spellings, and without this
    they match nothing at all.
    """
    return normalize(name).replace(" ", "")


def search_terms(row: dict[str, Any]) -> set[str]:
    """Every string that should match this exercise: name + aliases, each in
    both normalized and squashed form."""
    raw = [row.get("display_name") or "", *(row.get("aliases") or [])]
    terms: set[str] = set()
    for term in raw:
        for form in (normalize(str(term)), squash(str(term))):
            if form:
                terms.add(form)
    return terms


def matches_query(query: str, row: dict[str, Any]) -> bool:
    """Substring match, applied to folded text on both sides.

    Folding before the substring test is the whole fix: previously ``"bent over
    row"`` missed ``"Bent-over row hold"`` on the hyphen and ``"pushups"``
    missed ``"Push-ups"`` on the word break. A zero-hit search is exactly when a
    coach gives up and creates a duplicate.
    """
    forms = [form for form in (normalize(query), squash(query)) if form]
    if not forms:
        return False
    terms = search_terms(row)
    return any(form in term for form in forms for term in terms)


def find_duplicate_candidates(
    display_name: str,
    aliases: list[str] | None,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rows that are the same movement under a different spelling.

    Matches on **exact normalized equality** of any name/alias on either side —
    not fuzzy similarity. That distinction is load-bearing: a fuzzy guard would
    block "incline push-up" because "push-up" exists, which is a legitimate new
    variant. Near-duplicates stay advisory in the audit report, where a human
    reads them.
    """
    incoming = search_terms({"display_name": display_name, "aliases": aliases or []})
    if not incoming:
        return []
    return [row for row in rows if incoming & search_terms(row)]
