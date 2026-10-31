from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.session import get_session
from takehome.services.reviews import ReviewDetail, ReviewSummary, get_review, list_latest_reviews

router = APIRouter(tags=["reviews"])


@router.get("/api/risk-reviews", response_model=list[ReviewSummary])
async def list_risk_reviews(session: AsyncSession = Depends(get_session)) -> list[ReviewSummary]:
    """The latest risk review of each document, most recent first."""
    return await list_latest_reviews(session)


@router.get("/api/risk-reviews/{review_id}", response_model=ReviewDetail)
async def get_risk_review(
    review_id: str, session: AsyncSession = Depends(get_session)
) -> ReviewDetail:
    review = await get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Risk review not found")
    return review
