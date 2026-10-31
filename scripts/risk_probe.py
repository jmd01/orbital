"""Throwaway probe: how well does the model extract risks with verifiable quotes?

For each sample PDF, asks the model for structured risks, then checks in code whether
each quote appears in the extracted text and whether the claimed page matches where it
was actually found.

Run from the repo root:
    uv run python scripts/risk_probe.py [model] [pdf ...]
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Literal

import fitz
from pydantic import BaseModel
from pydantic_ai import Agent

from dotenv import load_dotenv

load_dotenv()  # exports ANTHROPIC_API_KEY from .env


class Risk(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"]
    category: str
    summary: str
    quote: str  # verbatim, max ~25 words
    page: int  # the "--- Page N ---" marker the quote sits under


class RiskReview(BaseModel):
    risks: list[Risk]


PROMPT = (
    "You are reviewing a document for a commercial real estate lawyer doing due diligence. "
    "Identify the material risks. For each, give severity, a short category, a title, a "
    "one-to-two sentence summary of why it matters, a VERBATIM quote of at most 25 words "
    "copied exactly from the document, and the page number from the '--- Page N ---' "
    "marker that the quote appears under (use the marker, not any printed page number).\n\n"
    "<document>\n{text}\n</document>"
)


def extract_pages(path: Path) -> list[str]:
    with fitz.open(path) as doc:
        return [page.get_text() for page in doc]  # type: ignore[union-attr]


def norm(s: str) -> str:
    """Collapse whitespace/hyphenation/quote styles so PDF line breaks don't cause misses."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"-\s*\n\s*", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def find_page(quote: str, pages: list[str]) -> int | None:
    q = norm(quote)
    if not q:
        return None
    for i, p in enumerate(pages, start=1):
        if q in norm(p):
            return i
    return None


async def probe(path: Path, model: str) -> None:
    pages = extract_pages(path)
    text = "\n\n".join(f"--- Page {i} ---\n{t}" for i, t in enumerate(pages, start=1) if t.strip())
    print(f"\n=== {path.name}: {len(pages)} pages, {len(text)} chars ===")
    if not text.strip():
        print("NO EXTRACTABLE TEXT (scanned PDF?)")
        return

    agent = Agent(model, output_type=RiskReview)
    result = await agent.run(PROMPT.format(text=text))
    risks = result.output.risks

    found = page_ok = 0
    for r in risks:
        actual = find_page(r.quote, pages)
        found += actual is not None
        page_ok += actual is not None and actual == r.page
        mark = "OK " if actual == r.page and actual else ("PG " if actual else "MISS")
        print(f"[{mark}] {r.severity:6} p{r.page}->{actual}  {r.title}")
        if actual is None:
            print(f"        quote: {r.quote!r}")
    n = len(risks) or 1
    print(
        f"-> {len(risks)} risks | quote found {found}/{len(risks)} ({found / n:.0%}) "
        f"| page correct {page_ok}/{len(risks)} ({page_ok / n:.0%})"
    )


async def main() -> None:
    args = sys.argv[1:]
    model = args[0] if args and not args[0].endswith(".pdf") else "anthropic:claude-haiku-4-5-20251001"
    paths = [Path(a) for a in args if a.endswith(".pdf")] or sorted(Path("sample-docs").glob("*.pdf"))
    for p in paths:
        await probe(p, model)


asyncio.run(main())
