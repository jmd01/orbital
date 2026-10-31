from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Document, Finding
from takehome.services.quote import locate_quote, split_pages

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


class FindingOut(BaseModel):
    """A saved finding, as sent to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    severity: Severity
    category: str
    summary: str
    quote: str
    page: int | None


class RiskTable(BaseModel):
    """A risk review: its findings plus severity counts. Sent to the frontend, never to the model."""

    review_id: str
    counts: dict[Severity, int]
    findings: list[FindingOut]


class RiskTablePart(BaseModel):
    """A risk table as a message part, as sent to clients (findings included)."""

    type: Literal["risk_table"] = "risk_table"
    version: Literal[1] = 1
    data: RiskTable


class StoredRiskTableData(BaseModel):
    review_id: str
    counts: dict[Severity, int]


class StoredRiskTablePart(BaseModel):
    """A risk table as stored on the message: a reference to the findings, not a copy."""

    type: Literal["risk_table"] = "risk_table"
    version: Literal[1] = 1
    data: StoredRiskTableData


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


async def save_review(
    session: AsyncSession, conversation_id: str, document_id: str, risks: list[RiskInput]
) -> RiskTable:
    """Store a review's risks as findings under a new review_id.

    Each finding's page is found by locating its quote in the document text; it is None when
    the quote can't be located.
    """
    review_id = uuid.uuid4().hex[:16]
    document = await session.get(Document, document_id)
    pages = split_pages(document.extracted_text) if document and document.extracted_text else {}
    rows = [
        Finding(
            review_id=review_id,
            conversation_id=conversation_id,
            document_id=document_id,
            position=position,
            title=risk.title,
            severity=risk.severity,
            category=risk.category,
            summary=risk.summary,
            quote=risk.quote,
            page=match.page if (match := locate_quote(risk.quote, pages)) else None,
        )
        for position, risk in enumerate(risks)
    ]
    session.add_all(rows)
    await session.commit()
    return RiskTable(
        review_id=review_id,
        counts=summarise_risks(risks).counts,
        findings=[FindingOut.model_validate(row) for row in rows],
    )


async def hydrate_parts(
    session: AsyncSession, stored_parts: list[dict[str, object]]
) -> list[RiskTablePart]:
    """Turn stored message parts into client parts by loading the findings they reference."""
    parts: list[RiskTablePart] = []
    for raw in stored_parts:
        stored = StoredRiskTablePart.model_validate(raw)
        result = await session.execute(
            select(Finding)
            .where(Finding.review_id == stored.data.review_id)
            .order_by(Finding.position)
        )
        findings = [FindingOut.model_validate(row) for row in result.scalars().all()]
        parts.append(
            RiskTablePart(
                data=RiskTable(
                    review_id=stored.data.review_id,
                    counts=stored.data.counts,
                    findings=findings,
                )
            )
        )
    return parts
