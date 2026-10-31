from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Document, Finding
from takehome.db.session import get_session
from takehome.services.highlight import HighlightBox, highlight_boxes

router = APIRouter(tags=["findings"])


@router.get("/api/findings/{finding_id}/highlights", response_model=list[HighlightBox])
async def get_finding_highlights(
    finding_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[HighlightBox]:
    """Where a finding's quote sits on its page. Empty when it has no page or can't be matched.

    Looked up by finding rather than by quote, so document text never travels in a URL.
    """
    finding = await session.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    document = await session.get(Document, finding.document_id)
    if finding.page is None or document is None or not os.path.exists(document.file_path):
        return []
    return highlight_boxes(document.file_path, finding.page, finding.quote)
