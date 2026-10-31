from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

import structlog
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolReturn,
)

from takehome.config import settings  # noqa: F401 — triggers ANTHROPIC_API_KEY export
from takehome.services.risk import RiskInput, RiskTable, summarise_risks

logger = structlog.get_logger()


@dataclass
class TextChunk:
    """A piece of the assistant's streamed text reply."""

    text: str


ChatEvent = TextChunk | RiskTable

agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=(
        "You are a helpful legal document assistant for commercial real estate lawyers. "
        "You help lawyers review and understand documents during due diligence.\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "- Answer questions based on the document content provided.\n"
        "- When referencing specific parts of the document, cite the relevant section or clause.\n"
        "- If the answer is not in the document, say so clearly. Do not fabricate information.\n"
        "- Be concise and precise. Lawyers value accuracy over verbosity.\n"
        "- When you reference specific content, mention the section, clause, or page.\n"
        "- When the user asks for a risk review (or to list, assess or flag risks), call the "
        "present_risks tool exactly once with every material risk you find, instead of writing "
        "the list out. The tool displays the table to the user. Afterwards reply with a brief "
        "summary of the headline findings; do not repeat the table."
    ),
)


@agent.tool_plain
def present_risks(risks: list[RiskInput]) -> ToolReturn:
    """Present the risks found in the document to the user as a table.

    Call once, with all material risks. Each quote must be copied verbatim from the document.
    """
    # Stage 1 stub: no validation or persistence yet, just prove the model calls the tool.
    logger.info("present_risks called", risk_count=len(risks), titles=[r.title for r in risks])
    summary = summarise_risks(risks)
    return ToolReturn(
        # What the model sees: compact, enough to write a specific summary.
        return_value=summary.model_dump(),
        # What the app sees: the full table, delivered to the frontend by the stream.
        metadata=RiskTable(risks=risks, counts=summary.counts),
    )


async def generate_title(user_message: str) -> str:
    """Generate a 3-5 word conversation title from the first user message."""
    result = await agent.run(
        f"Generate a concise 3-5 word title for a conversation that starts with: '{user_message}'. "
        "Return only the title, nothing else."
    )
    title = str(result.output).strip().strip('"').strip("'")
    # Truncate if too long
    if len(title) > 100:
        title = title[:97] + "..."
    return title


async def chat_with_document(
    user_message: str,
    document_text: str | None,
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[ChatEvent]:
    """Stream a response to the user's message, yielding text chunks and tool output.

    Builds a prompt that includes document context and conversation history,
    then streams the response from the LLM.
    """
    # Build the full prompt with context
    prompt_parts: list[str] = []

    # Add document context if available
    if document_text:
        prompt_parts.append(
            "The following is the content of the document being discussed:\n\n"
            "<document>\n"
            f"{document_text}\n"
            "</document>\n"
        )
    else:
        prompt_parts.append(
            "No document has been uploaded yet. If the user asks about a document, "
            "let them know they need to upload one first.\n"
        )

    # Add conversation history
    if conversation_history:
        prompt_parts.append("Previous conversation:\n")
        for msg in conversation_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")
        prompt_parts.append("\n")

    # Add the current user message
    prompt_parts.append(f"User: {user_message}")

    full_prompt = "\n".join(prompt_parts)

    async with agent.run_stream_events(full_prompt) as events:
        async for event in events:
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if event.part.content:
                    yield TextChunk(event.part.content)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                yield TextChunk(event.delta.content_delta)
            elif isinstance(event, FunctionToolResultEvent) and isinstance(
                event.part.metadata, RiskTable
            ):
                yield event.part.metadata


def count_sources_cited(response: str) -> int:
    """Count the number of references to document sections, clauses, pages, etc."""
    patterns = [
        r"section\s+\d+",
        r"clause\s+\d+",
        r"page\s+\d+",
        r"paragraph\s+\d+",
    ]
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, response, re.IGNORECASE))
    return count
