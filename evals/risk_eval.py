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
import json
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
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "evals" / "results"
LLM_FILE = ROOT / "backend" / "src" / "takehome" / "services" / "llm.py"

load_dotenv(ROOT / ".env")
# Outside Docker the app's Settings rejects the extra keys in .env, so import it from a
# directory without a .env. The API key is already exported by load_dotenv above.
os.chdir(tempfile.gettempdir())
sys.path.insert(0, str(ROOT / "backend" / "src"))

import fitz  # noqa: E402
from pydantic_ai.messages import ToolCallPart  # noqa: E402

from takehome.services.llm import agent  # noqa: E402

REQUEST = "Run a risk review of this document"
CONCURRENCY = 3


def norm(s: str) -> str:
    """Collapse whitespace, hyphenated line breaks and curly quotes so PDF layout can't cause misses."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"-\s*\n\s*", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def load_pages(path: Path) -> list[str]:
    with fitz.open(path) as doc:
        return [norm(page.get_text()) for page in doc]  # type: ignore[union-attr]


def build_prompt(path: Path) -> str:
    """Same shape as chat_with_document(): page-marked document text, then the user message."""
    with fitz.open(path) as doc:
        pages = [
            f"--- Page {i} ---\n{page.get_text()}"  # type: ignore[union-attr]
            for i, page in enumerate(doc, start=1)
        ]
    return (
        "The following is the content of the document being discussed:\n\n"
        f"<document>\n{chr(10).join(pages)}\n</document>\n\nUser: {REQUEST}"
    )


def locate(quote: str, pages: list[str]) -> tuple[str, int | None]:
    """exact: whole quote found. anchor: its first six words found. none: not located."""
    q = norm(quote)
    if not q:
        return "none", None
    for i, page in enumerate(pages, start=1):
        if q in page:
            return "exact", i
    anchor = " ".join(q.split()[:6])
    for i, page in enumerate(pages, start=1):
        if anchor in page:
            return "anchor", i
    return "none", None


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


async def run_once(path: Path, pages: list[str], sem: asyncio.Semaphore) -> dict[str, Any]:
    async with sem:
        start = time.monotonic()
        try:
            result = await agent.run(build_prompt(path))
        except Exception as exc:  # record failures instead of aborting the whole eval
            return {"error": repr(exc), "tool_calls": 0, "risks": []}
        secs = time.monotonic() - start

    calls = [
        p
        for m in result.all_messages()
        for p in getattr(m, "parts", [])
        if isinstance(p, ToolCallPart)
    ]
    risks: list[dict[str, Any]] = []
    for call in calls:
        risks.extend(call.args_as_dict().get("risks", []))

    located = []
    for r in risks:
        kind, page = locate(r.get("quote", ""), pages)
        located.append({**r, "match": kind, "page": page})

    n = len(risks)
    kinds = [r["match"] for r in located]
    text = str(result.output)
    severity = {
        s: sum(1 for r in risks if r.get("severity") == s) for s in ("high", "medium", "low")
    }
    stated = stated_counts(text)
    mismatch = ("total" in stated and stated["total"] != n) or (
        "high" in stated and stated["high"] != severity["high"]
    )
    return {
        "tool_calls": len(calls),
        "risk_count": n,
        "severity": severity,
        "exact": kinds.count("exact"),
        "anchor": kinds.count("anchor"),
        "unlocated": kinds.count("none"),
        "stated_counts": stated,
        "count_mismatch": mismatch,
        "seconds": round(secs, 1),
        "risks": located,
        "final_text": text,
    }


def title_stability(runs: list[dict[str, Any]]) -> float | None:
    """Share of run-1 titles that have a similar title in every other run (ratio >= 0.55)."""
    titled = [[r["title"] for r in run["risks"]] for run in runs if run.get("risks")]
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


def summarise(runs: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in runs if "error" not in r]
    risks = sum(r["risk_count"] for r in ok) or 1
    return {
        "runs": len(runs),
        "errors": len(runs) - len(ok),
        "tool_called_once": sum(r["tool_calls"] == 1 for r in ok),
        "risk_count": [r["risk_count"] for r in ok],
        "exact_rate": sum(r["exact"] for r in ok) / risks,
        "located_rate": sum(r["exact"] + r["anchor"] for r in ok) / risks,
        "summary_checked": sum(bool(r["stated_counts"]) for r in ok),
        "summary_count_mismatches": sum(r["count_mismatch"] for r in ok),
        "title_stability": title_stability(ok),
        "mean_seconds": round(mean(r["seconds"] for r in ok), 1) if ok else None,
    }


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def to_markdown(meta: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> str:
    lines = [
        f"# Risk eval {meta['timestamp']}",
        "",
        f"- model: `{meta['model']}` · runs per doc: {meta['runs_per_doc']}",
        f"- commit: `{meta['commit']}`{' (dirty)' if meta['dirty'] else ''} · llm.py hash: `{meta['llm_hash']}`",
        "",
        "| Document | Tool called once | Risks per run | Exact quote | Located (exact+anchor) | "
        "Counts stated in summary | Title stability | Avg s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, s in summaries.items():
        stab = "n/a" if s["title_stability"] is None else f"{s['title_stability']:.0%}"
        lines.append(
            f"| {name} | {s['tool_called_once']}/{s['runs']} | {s['risk_count']} | "
            f"{s['exact_rate']:.0%} | {s['located_rate']:.0%} | "
            f"{s['summary_count_mismatches']} wrong of {s['summary_checked']} checked | {stab} | {s['mean_seconds']} |"
        )
    lines += [
        "",
        "Exact = whole quote found in the PDF text. Anchor = first six words found (model tidied the "
        "rest). Counts stated in summary = the model's prose ('N risks', 'three high-severity') compared with the tool's own counts; only summaries that state a count can be checked (regex heuristic, so occasional false positives). "
        "Title stability = share of run-1 risk titles matched in every other run.",
        "",
    ]
    return "\n".join(lines)


async def main() -> None:
    runs_per_doc = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    pdfs = sorted((ROOT / "sample-docs").glob("*.pdf"))
    sem = asyncio.Semaphore(CONCURRENCY)

    async def do_doc(path: Path) -> tuple[str, list[dict[str, Any]]]:
        pages = load_pages(path)
        runs = await asyncio.gather(*(run_once(path, pages, sem) for _ in range(runs_per_doc)))
        return path.name, list(runs)

    results = dict(await asyncio.gather(*(do_doc(p) for p in pdfs)))
    summaries = {name: summarise(runs) for name, runs in results.items()}

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    meta = {
        "timestamp": stamp,
        "model": str(agent.model.model_name) if agent.model else "unknown",  # type: ignore[union-attr]
        "runs_per_doc": runs_per_doc,
        "commit": git("rev-parse", "--short", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
        "llm_hash": hashlib.sha256(LLM_FILE.read_bytes()).hexdigest()[:8],
        "request": REQUEST,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{stamp}.json").write_text(
        json.dumps({"meta": meta, "summaries": summaries, "runs": results}, indent=2)
    )
    markdown = to_markdown(meta, summaries)
    (RESULTS_DIR / f"{stamp}.md").write_text(markdown)
    print(markdown)
    print(f"Saved evals/results/{stamp}.json and .md")


asyncio.run(main())
