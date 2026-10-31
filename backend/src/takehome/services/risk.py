from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]


class RiskInput(BaseModel):
    """One risk as reported by the model.

    There is deliberately no page field: the model's page attribution is unreliable, so the
    page is derived later by locating the quote in the document text.
    """

    title: str = Field(description="Short headline, e.g. 'Upward-only rent review with no cap'")
    severity: Severity = Field(description="How serious this is for the client")
    category: str = Field(description="Short topic label, e.g. 'Rent', 'Title', 'Environmental'")
    summary: str = Field(description="One or two sentences on why this matters")
    quote: str = Field(
        description="Verbatim text copied exactly from the document, one sentence or fragment, "
        "at most 25 words. Do not paraphrase."
    )


class RiskTable(BaseModel):
    """The full table of risks presented to the user. Sent to the frontend, never to the model."""

    risks: list[RiskInput]
    counts: dict[Severity, int]


class RiskToolResult(BaseModel):
    """What the model gets back from the tool. Compact: enough to write a specific summary."""

    accepted: int
    counts: dict[Severity, int]
    top: list[str]


def summarise_risks(risks: list[RiskInput]) -> RiskToolResult:
    counts: dict[Severity, int] = {"high": 0, "medium": 0, "low": 0}
    for risk in risks:
        counts[risk.severity] += 1
    # Worst first, so the model names the most serious issues in its reply.
    order = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(risks, key=lambda r: order[r.severity])
    return RiskToolResult(accepted=len(risks), counts=counts, top=[r.title for r in ranked[:3]])
