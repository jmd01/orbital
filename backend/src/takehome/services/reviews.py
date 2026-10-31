"""Read side of risk reviews: the latest review per document, and a single review in full."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Document, Finding
from takehome.services.risk import FindingOut, RiskTable, Severity

_severity = TypeAdapter(Severity)


class ReviewSummary(BaseModel):
    """One entry in the Risk reviews list."""

    review_id: str
    conversation_id: str
    document_id: str
    document_filename: str
    created_at: datetime
    counts: dict[Severity, int]
    total: int


class ReviewDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    filename: str
    page_count: int
    uploaded_at: datetime


class ReviewDetail(BaseModel):
    """A whole review, with the document it was run on, for the full-page view."""

    conversation_id: str
    created_at: datetime
    document: ReviewDocument
    table: RiskTable


def _empty_counts() -> dict[Severity, int]:
    return {"high": 0, "medium": 0, "low": 0}


async def list_latest_reviews(session: AsyncSession) -> list[ReviewSummary]:
    """The newest review of each document, most recent first."""
    stmt = (
        select(
            Finding.review_id,
            Finding.conversation_id,
            Finding.document_id,
            Document.filename,
            func.min(Finding.created_at),
            Finding.severity,
            func.count(),
        )
        .join(Document, Document.id == Finding.document_id)
        .group_by(
            Finding.review_id,
            Finding.conversation_id,
            Finding.document_id,
            Document.filename,
            Finding.severity,
        )
    )
    reviews: dict[str, ReviewSummary] = {}
    for review_id, conversation_id, document_id, filename, created_at, severity, count in (
        await session.execute(stmt)
    ).all():
        review = reviews.setdefault(
            review_id,
            ReviewSummary(
                review_id=review_id,
                conversation_id=conversation_id,
                document_id=document_id,
                document_filename=filename,
                created_at=created_at,
                counts=_empty_counts(),
                total=0,
            ),
        )
        review.counts[_severity.validate_python(severity)] += count
        review.total += count

    latest: dict[str, ReviewSummary] = {}
    for review in reviews.values():
        current = latest.get(review.document_id)
        if current is None or review.created_at > current.created_at:
            latest[review.document_id] = review
    return sorted(latest.values(), key=lambda r: r.created_at, reverse=True)


async def get_review(session: AsyncSession, review_id: str) -> ReviewDetail | None:
    result = await session.execute(
        select(Finding).where(Finding.review_id == review_id).order_by(Finding.position)
    )
    rows = list(result.scalars().all())
    if not rows:
        return None
    document = await session.get(Document, rows[0].document_id)
    if document is None:
        return None

    findings = [FindingOut.model_validate(row) for row in rows]
    counts = _empty_counts()
    for finding in findings:
        counts[finding.severity] += 1
    return ReviewDetail(
        conversation_id=rows[0].conversation_id,
        created_at=min(row.created_at for row in rows),
        document=ReviewDocument.model_validate(document),
        table=RiskTable(review_id=review_id, counts=counts, findings=findings),
    )
