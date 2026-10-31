"""Find where a quote sits in a document, so findings get a page number from the text itself.

The model's own page attribution is unreliable, so pages are derived here instead.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

# document.py writes extracted text as "--- Page N ---\n<text>" blocks.
PAGE_MARKER = re.compile(r"--- Page (\d+) ---\n")
ANCHOR_WORDS = 6
ELLIPSIS = re.compile(r"\.\.\.|\u2026")  # the model joins fragments with "..."


class QuoteMatch(BaseModel):
    page: int
    exact: bool  # True: the whole quote was found. False: only its opening words were.


def normalise(text: str) -> str:
    """Collapse whitespace, hyphenated line breaks and curly quotes, so PDF layout can't cause misses."""
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def split_pages(extracted_text: str) -> dict[int, str]:
    """Map page number to normalised page text. Page numbers come from the markers."""
    parts = PAGE_MARKER.split(extracted_text)  # [before, "1", text, "2", text, ...]
    return {int(parts[i]): normalise(parts[i + 1]) for i in range(1, len(parts) - 1, 2)}


def locate_quote(quote: str, pages: dict[int, str]) -> QuoteMatch | None:
    """Page of the whole quote if found, else of its first six words, else None.

    The opening-words fallback covers quotes the model tidied or stitched with '...' (it stops at
    the first one).
    """
    needle = normalise(quote)
    if not needle:
        return None
    for number, text in pages.items():
        if needle in text:
            return QuoteMatch(page=number, exact=True)
    opening = ELLIPSIS.split(needle)[0]
    anchor = " ".join(opening.split()[:ANCHOR_WORDS])
    for number, text in pages.items():
        if anchor in text:
            return QuoteMatch(page=number, exact=False)
    return None
