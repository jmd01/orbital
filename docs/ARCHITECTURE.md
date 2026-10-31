# Risk Review: Architecture & Implementation

## Goal
Turn "run a risk review" from a wall of numbered text into a structured, verifiable table inside
the existing chat: severity, category, summary, the exact quote, and the page it came from.
Lawyers can scan it, filter it, and check every finding against the source.

## Scope
- **Phase 1 (core):** single-document risk review in the existing conversation.
- **Stretch:** jump-to-page in the viewer, stronger-model validator, `ask_user` (buyer / tenant /
  lender), findings panel per document, multiple documents per conversation.
- **Future:** `Deal` entity owning documents, findings and conversations; portfolio dashboard.

## Flow
```
user: "run a risk review"
  -> agent reads document, calls present_risks(risks[])          (PydanticAI tool)
       -> tool validates (quote located in PDF text, page derived in code)
       -> tool inserts findings under a new review_id
       -> tool returns {review_id, counts, top titles, rejected[]} to the model
  -> model writes a short summary of what was found
  -> SSE stream emits: content* ... part{risk_table} ... message ... done
  -> assistant message saved with parts=[{type:risk_table, data:{review_id, counts}}]
  -> frontend renders <RiskTable> from the hydrated findings
```

## Data model
`messages` gains `parts` (JSON list, default `[]`): typed, versioned entries
`{type, version, data}`. Text stays in `content` (chat history is unchanged); parts carry
rich output. New rich outputs are additive: one union member, one component.

New `findings` table:
`id, review_id, conversation_id, document_id, position, title, severity, category, summary, quote,
page, created_at`. `position` keeps display order. `page` is nullable: it is derived in code from
the quote, never supplied by the model (stage 7). `verification_status` / `review_status` are
deferred until something reads them.
`review_id` is a generated UUID, not a table. "Latest review for a document" = findings of the
newest `review_id` for that `document_id`. The stored message part is a reference
`{type, version, data:{review_id, counts}}`; the API hydrates it into the full table
(`RiskTablePart`) on `GET /messages` and in the stream's `message` event, so the chat renders from
one response. Stored and client shapes are separate Pydantic models in `services/risk.py`.

## Tool contract (`present_risks`)
- **Input (from model):** `risks: [{title, severity, category, summary, quote}]`. No page number:
  the model's page attribution is unreliable (probe: wrong near page boundaries), so the page is
  derived deterministically.
- **Returned to model:** `{review_id, accepted, counts, top[], rejected[{title, reason}]}`.
  Compact on purpose: enough for a specific summary and a retry, no table data to retype.
- **To the frontend:** the backend, not the model, emits the saved table. The tool returns a
  `ToolReturn` whose `metadata` (a typed `RiskTable`) the stream forwards as a `risk_table` event.
- **Saving:** the tool gets a typed `save_review` function through the agent's deps (`ChatDeps`), so
  it never touches the database directly and evals can pass an in-memory fake.

## Quality layers (applied in this order)
1. Structured output via Pydantic schema.
2. Deterministic quote location: normalise whitespace / hyphenation / quotes, exact match per page,
   fuzzy fallback (`rapidfuzz`, ~85). Page comes from the match. No match -> `unverified`.
3. Severity counts computed in code (never asked of the model).
4. Stretch: stronger-model validator per finding on quote + surrounding context, rejections fed back
   to the agent (`ModelRetry`).

Probe result (`scripts/risk_probe.py`, Haiku 4.5, 3 sample PDFs): 18/22 quotes matched exactly;
the 4 misses were tidied/completed quotes of real content, not inventions.

## Build stages (one commit each)
1. Risk models + stub `present_risks` tool; prompt trigger. *See the model call it in logs.*
2. Tool-aware streaming in `llm.py` (typed items). *Plain chat still works.*
3. `messages.py` emits a `part` SSE event. *Visible with `curl -N`.*
4. `findings` table, `messages.parts`, migration, schemas, hydration. *Survives refresh.*
5. Frontend plumbing: types, `use-messages.ts` branch. *Payload visible in console.*
6. `RiskTable` component (table -> chips, expandable rows, filters).
7. Quality: `locate_quote`, fuzzy fallback, verified/unverified badge.
8. Stretch items (jump-to-page, validator, `ask_user`, findings panel, multi-document).
9. Tests, agreed one by one before any are written (see below).
10. If time allows: compare models (e.g. Haiku vs a stronger model) with `evals/risk_eval.py`.
11. `just check`, README / DECISIONS, Loom.

## Testing approach
Deliberately small. Tests are proposed and agreed before they are written, so each one can be
explained. Backend tests live in `backend/tests/` (currently empty). The frontend has no test
runner yet; adding one is itself a decision to take, not a default.
Likely candidates, to be confirmed: quote normalisation / `locate_quote` (pure logic, the
trust-critical part), severity counting in `summarise_risks`, and the `parts` serialisation.
Model quality is covered by `evals/`, not unit tests.

## Known trade-offs
- Findings are inserted by the tool mid-stream, so a failed stream can leave orphaned findings.
  Accepted for this scope; harmless (no message part references them).
- Scanned PDFs have no extractable text, so quote location is impossible without OCR.
- JSON `parts` have no DB-level constraints; Pydantic validation on write is the guard.
