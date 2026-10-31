"""Find where a quote sits on its page, as rectangles the viewer can draw a highlight over.

Matching is done on the page's own word positions, so it needs no fuzzy search and is not
thrown by line breaks, quotation marks or other punctuation.
"""

from __future__ import annotations

import re

import fitz  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel

from takehome.services.quote import ANCHOR_WORDS, ELLIPSIS


class Word(BaseModel):
    text: str  # normalised: lowercase, punctuation removed
    block: int
    line: int
    x0: float
    y0: float
    x1: float
    y1: float


class HighlightBox(BaseModel):
    """A rectangle as fractions of the page size, so it scales to any rendered width."""

    x0: float
    y0: float
    x1: float
    y1: float


def normalise_word(raw: str) -> str:
    return re.sub(r"\W", "", raw.lower())


def read_page_words(file_path: str, page_number: int) -> tuple[list[Word], float, float]:
    """The words on a page with their positions, plus the page width and height.

    The only place the untyped PDF library is touched. Words that are only punctuation are
    dropped, and page_number is 1-based.
    """
    with fitz.open(file_path) as doc:  # pyright: ignore
        page = doc[page_number - 1]  # pyright: ignore
        raw_words = page.get_text("words")  # pyright: ignore
        words = [
            Word(
                text=text,
                block=int(w[5]),  # pyright: ignore
                line=int(w[6]),  # pyright: ignore
                x0=float(w[0]),  # pyright: ignore
                y0=float(w[1]),  # pyright: ignore
                x1=float(w[2]),  # pyright: ignore
                y1=float(w[3]),  # pyright: ignore
            )
            for w in raw_words  # pyright: ignore
            if (text := normalise_word(str(w[4])))  # pyright: ignore
        ]
        return words, float(page.rect.width), float(page.rect.height)  # pyright: ignore


def _find_sequence(words: list[Word], wanted: list[str]) -> list[Word]:
    if not wanted:
        return []
    texts = [w.text for w in words]
    for start in range(len(texts) - len(wanted) + 1):
        if texts[start : start + len(wanted)] == wanted:
            return words[start : start + len(wanted)]
    return []


def match_words(words: list[Word], quote: str) -> list[Word]:
    """The words of the whole quote if found in order, else of its opening words."""
    whole = [t for part in quote.split() if (t := normalise_word(part))]
    opening = [t for part in ELLIPSIS.split(quote)[0].split() if (t := normalise_word(part))]
    return _find_sequence(words, whole) or _find_sequence(words, opening[:ANCHOR_WORDS])


def to_boxes(matched: list[Word], width: float, height: float) -> list[HighlightBox]:
    """One box per line of text, so a multi-line quote highlights as it reads."""
    lines: dict[tuple[int, int], list[Word]] = {}
    for word in matched:
        lines.setdefault((word.block, word.line), []).append(word)
    return [
        HighlightBox(
            x0=min(w.x0 for w in group) / width,
            y0=min(w.y0 for w in group) / height,
            x1=max(w.x1 for w in group) / width,
            y1=max(w.y1 for w in group) / height,
        )
        for group in lines.values()
    ]


def highlight_boxes(file_path: str, page_number: int, quote: str) -> list[HighlightBox]:
    words, width, height = read_page_words(file_path, page_number)
    return to_boxes(match_words(words, quote), width, height)
