from __future__ import annotations

from takehome.services.quote import locate_quote, split_pages

# Same "--- Page N ---" format that document.py stores. Note the hyphenated line break on page 1.
EXTRACTED_TEXT = (
    "--- Page 1 ---\n"
    "The Tenant shall pay the rent\nwithout any deduc-\ntion whatsoever.\n\n"
    "--- Page 3 ---\n"
    "Break clause: the Tenant may terminate on notice.\n"
)


def test_finds_whole_quote_across_a_hyphenated_line_break() -> None:
    pages = split_pages(EXTRACTED_TEXT)

    match = locate_quote("shall pay the rent without any deduction", pages)

    assert match is not None
    assert match.page == 1
    assert match.exact is True


def test_falls_back_to_opening_words_when_the_model_stitches_fragments() -> None:
    pages = split_pages(EXTRACTED_TEXT)

    match = locate_quote("The Tenant may terminate... and some other words", pages)

    assert match is not None
    assert match.page == 3
    assert match.exact is False


def test_returns_none_for_a_missing_or_empty_quote() -> None:
    pages = split_pages(EXTRACTED_TEXT)

    assert locate_quote("a completely unrelated sentence here", pages) is None
    assert locate_quote("   ", pages) is None
