from __future__ import annotations

import pytest

from takehome.services.highlight import Word, match_words, normalise_word, to_boxes


def page_words(text: str) -> list[Word]:
    """Words as read_page_words() returns them: normalised, one line, laid out left to right."""
    return [
        Word(text=normalise_word(raw), block=0, line=0, x0=i * 10, y0=0, x1=i * 10 + 8, y1=10)
        for i, raw in enumerate(text.split())
    ]


def test_match_ignores_punctuation_and_falls_back_to_the_opening_words() -> None:
    # The document writes: "the Insured Risks" means fire, lightning, explosion
    words = page_words('"the Insured Risks" means fire, lightning, explosion')

    # The model dropped the quotation marks and the commas; the words still match in order.
    whole = match_words(words, "the Insured Risks means fire lightning")
    assert [w.text for w in whole] == ["the", "insured", "risks", "means", "fire", "lightning"]

    # An invented ending defeats the whole-quote match, so only the first six words are matched.
    opening = match_words(
        words, "the Insured Risks means fire, lightning, and some invented ending"
    )
    assert [w.text for w in opening] == ["the", "insured", "risks", "means", "fire", "lightning"]


def test_boxes_are_one_per_line_and_scaled_to_fractions_of_the_page() -> None:
    matched = [
        Word(text="a", block=0, line=0, x0=100, y0=200, x1=150, y1=212),
        Word(text="b", block=0, line=0, x0=155, y0=200, x1=200, y1=212),
        Word(text="c", block=0, line=1, x0=100, y0=216, x1=180, y1=228),
    ]

    boxes = to_boxes(matched, width=400, height=800)

    assert len(boxes) == 2
    first, second = boxes
    # Two words on the same line merge into one box.
    assert (first.x0, first.y0, first.x1, first.y1) == pytest.approx((0.25, 0.25, 0.5, 0.265))
    assert (second.x0, second.y0, second.x1, second.y1) == pytest.approx((0.25, 0.27, 0.45, 0.285))
