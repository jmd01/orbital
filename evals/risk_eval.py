"""Risk-review eval: run the real agent + present_risks tool repeatedly over the sample PDFs.

For every document and run it records whether the tool was called, how many risks came back,
whether each quote can be located in the PDF text, and whether the model's written summary
agrees with the tool's own counts. Results are saved under evals/results/ so quality can be
compared across prompt / model / code changes.

Run from the repo root:
    uv run python evals/risk_eval.py [runs_per_doc]
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean
from typing import Literal

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "evals" / "results"
# Files that hold what the model is told: the system prompt and the tool schema descriptions.
PROMPT_FILES = [
    ROOT / "backend" / "src" / "takehome" / "services" / "llm.py",
    ROOT / "backend" / "src" / "takehome" / "services" / "risk.py",
]

load_dotenv(ROOT / ".env")
# Outside Docker the app's Settings rejects the extra keys in .env, so import it from a
# directory without a .env. The API key is already exported by load_dotenv above.
os.chdir(tempfile.gettempdir())
sys.path.insert(0, str(ROOT / "backend" / "src"))

import fitz  # noqa: E402  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel  # noqa: E402
from pydantic_ai.messages import ToolCallPart  # noqa: E402

from takehome.services.llm import ChatDeps, agent  # noqa: E402
from takehome.services.quote import locate_quote, split_pages  # noqa: E402
from takehome.services.risk import (  # noqa: E402
    FindingOut,
    RiskInput,
    RiskTable,
    Severity,
    summarise_risks,
)

REQUEST = "Run a risk review of this document"
CONCURRENCY = 3
MatchKind = Literal["exact", "anchor", "none"]


class RiskToolArgs(BaseModel):
    """The arguments the model passed to present_risks."""

    risks: list[RiskInput]


class LocatedRisk(RiskInput):
    match: MatchKind
    page: int | None


class RunResult(BaseModel):
    error: str | None = None
    tool_calls: int = 0
    risk_count: int = 0
    severity: dict[Severity, int] = {}
    exact: int = 0
    anchor: int = 0
    unlocated: int = 0
    stated_counts: dict[str, int] = {}
    count_mismatch: bool = False
    seconds: float = 0.0
    risks: list[LocatedRisk] = []
    final_text: str = ""


class DocSummary(BaseModel):
    runs: int
    errors: int
    tool_called_once: int
    risk_count: list[int]
    exact_rate: float
    located_rate: float
    summary_checked: int
    summary_count_mismatches: int
    title_stability: float | None
    mean_seconds: float | None


class Meta(BaseModel):
    timestamp: str
    model: str
    runs_per_doc: int
    commit: str
    dirty: bool
    prompt_hash: str
    request: str


class EvalReport(BaseModel):
    meta: Meta
    summaries: dict[str, DocSummary]
    runs: dict[str, list[RunResult]]


async def fake_save_review(risks: list[RiskInput]) -> RiskTable:
    """Stand-in for the database save, so evals never touch Postgres."""
    return RiskTable(
        review_id="eval",
        counts=summarise_risks(risks).counts,
        findings=[
            FindingOut(id=str(i), page=None, **risk.model_dump()) for i, risk in enumerate(risks)
        ],
    )


def raw_page_texts(path: Path) -> list[str]:
    """Raw text of each PDF page. The only place the untyped PDF library is touched."""
    with fitz.open(path) as doc:  # pyright: ignore[reportUnknownVariableType]
        return [str(page.get_text()) for page in doc]  # pyright: ignore


def extracted_text(path: Path) -> str:
    """Same format document.py stores: page-marked text, blank pages skipped."""
    return "\n\n".join(
        f"--- Page {i} ---\n{text}"
        for i, text in enumerate(raw_page_texts(path), start=1)
        if text.strip()
    )


def build_prompt(path: Path) -> str:
    """Same shape as chat_with_document(): the document text, then the user message."""
    return (
        "The following is the content of the document being discussed:\n\n"
        f"<document>\n{extracted_text(path)}\n</document>\n\nUser: {REQUEST}"
    )


def locate(quote: str, pages: dict[int, str]) -> tuple[MatchKind, int | None]:
    """The app's own locator; the exact / anchor split is only kept for reporting."""
    match = locate_quote(quote, pages)
    if match is None:
        return "none", None
    return ("exact" if match.exact else "anchor"), match.page


NUMBER_WORDS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen".split()
    )
}
NUMBER = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else NUMBER_WORDS[token.lower()]


def stated_counts(text: str) -> dict[str, int]:
    """Heuristic: counts the model states in prose, e.g. '10 risks', 'three high-severity risks'."""
    found: dict[str, int] = {}
    if m := re.search(NUMBER + r"\s+(?:\w+\s+){0,2}?risks", text, re.IGNORECASE):
        found["total"] = _to_int(m.group(1))
    if m := re.search(
        NUMBER + r"\s+(?:\*\*)?high[- ](?:severity|risk|priority)?", text, re.IGNORECASE
    ):
        found["high"] = _to_int(m.group(1))
    return found


async def run_once(path: Path, pages: dict[int, str], sem: asyncio.Semaphore) -> RunResult:
    async with sem:
        start = time.monotonic()
        try:
            result = await agent.run(
                build_prompt(path), deps=ChatDeps(save_review=fake_save_review)
            )
        except Exception as exc:  # record failures instead of aborting the whole eval
            return RunResult(error=repr(exc))
        secs = time.monotonic() - start

    calls = [
        part
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolCallPart)
    ]
    risks = [
        risk for call in calls for risk in RiskToolArgs.model_validate(call.args_as_dict()).risks
    ]

    located: list[LocatedRisk] = []
    for risk in risks:
        kind, page = locate(risk.quote, pages)
        located.append(LocatedRisk(**risk.model_dump(), match=kind, page=page))

    counts = summarise_risks(risks).counts
    text = str(result.output)
    stated = stated_counts(text)
    mismatch = ("total" in stated and stated["total"] != len(risks)) or (
        "high" in stated and stated["high"] != counts["high"]
    )
    return RunResult(
        tool_calls=len(calls),
        risk_count=len(risks),
        severity=counts,
        exact=sum(r.match == "exact" for r in located),
        anchor=sum(r.match == "anchor" for r in located),
        unlocated=sum(r.match == "none" for r in located),
        stated_counts=stated,
        count_mismatch=mismatch,
        seconds=round(secs, 1),
        risks=located,
        final_text=text,
    )


def title_stability(runs: list[RunResult]) -> float | None:
    """Share of run-1 titles that have a similar title in every other run (ratio >= 0.55)."""
    titled = [[r.title for r in run.risks] for run in runs if run.risks]
    if len(titled) < 2:
        return None
    hits = total = 0
    for title in titled[0]:
        for other in titled[1:]:
            total += 1
            best = max(
                (SequenceMatcher(None, title.lower(), o.lower()).ratio() for o in other), default=0
            )
            hits += best >= 0.55
    return hits / total if total else None


def summarise(runs: list[RunResult]) -> DocSummary:
    ok = [r for r in runs if r.error is None]
    risks = sum(r.risk_count for r in ok) or 1
    return DocSummary(
        runs=len(runs),
        errors=len(runs) - len(ok),
        tool_called_once=sum(r.tool_calls == 1 for r in ok),
        risk_count=[r.risk_count for r in ok],
        exact_rate=sum(r.exact for r in ok) / risks,
        located_rate=sum(r.exact + r.anchor for r in ok) / risks,
        summary_checked=sum(bool(r.stated_counts) for r in ok),
        summary_count_mismatches=sum(r.count_mismatch for r in ok),
        title_stability=title_stability(ok),
        mean_seconds=round(mean(r.seconds for r in ok), 1) if ok else None,
    )


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def to_markdown(meta: Meta, summaries: dict[str, DocSummary]) -> str:
    lines = [
        f"# Risk eval {meta.timestamp}",
        "",
        f"- model: `{meta.model}` · runs per doc: {meta.runs_per_doc}",
        f"- commit: `{meta.commit}`{' (dirty)' if meta.dirty else ''} · prompt hash: `{meta.prompt_hash}`",
        "",
        "| Document | Tool called once | Risks per run | Exact quote | Located (exact+anchor) | "
        "Counts stated in summary | Title stability | Avg s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, s in summaries.items():
        stab = "n/a" if s.title_stability is None else f"{s.title_stability:.0%}"
        lines.append(
            f"| {name} | {s.tool_called_once}/{s.runs} | {s.risk_count} | "
            f"{s.exact_rate:.0%} | {s.located_rate:.0%} | "
            f"{s.summary_count_mismatches} wrong of {s.summary_checked} checked | {stab} | {s.mean_seconds} |"
        )
    lines += [
        "",
        "Exact = whole quote found in the PDF text. Anchor = first six words found (model tidied the "
        "rest). Counts stated in summary = the model's prose ('N risks', 'three high-severity') "
        "compared with the tool's own counts; only summaries that state a count can be checked "
        "(regex heuristic, so occasional false positives). "
        "Title stability = share of run-1 risk titles matched in every other run.",
        "",
    ]
    return "\n".join(lines)


async def main() -> None:
    runs_per_doc = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    pdfs = sorted((ROOT / "sample-docs").glob("*.pdf"))
    sem = asyncio.Semaphore(CONCURRENCY)

    async def do_doc(path: Path) -> tuple[str, list[RunResult]]:
        pages = split_pages(extracted_text(path))
        runs = await asyncio.gather(*(run_once(path, pages, sem) for _ in range(runs_per_doc)))
        return path.name, list(runs)

    results = dict(await asyncio.gather(*(do_doc(p) for p in pdfs)))
    summaries = {name: summarise(runs) for name, runs in results.items()}

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    meta = Meta(
        timestamp=stamp,
        model=str(agent.model.model_name) if agent.model else "unknown",  # pyright: ignore
        runs_per_doc=runs_per_doc,
        commit=git("rev-parse", "--short", "HEAD"),
        dirty=bool(git("status", "--porcelain", "--untracked-files=no")),
        prompt_hash=hashlib.sha256(b"".join(f.read_bytes() for f in PROMPT_FILES)).hexdigest()[:8],
        request=REQUEST,
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = EvalReport(meta=meta, summaries=summaries, runs=results)
    (RESULTS_DIR / f"{stamp}.json").write_text(report.model_dump_json(indent=2))
    markdown = to_markdown(meta, summaries)
    (RESULTS_DIR / f"{stamp}.md").write_text(markdown)
    print(markdown)
    print(f"Saved evals/results/{stamp}.json and .md")


asyncio.run(main())
