# Risk Review: Architecture

How the structured risk review works, end to end. For why it's built this way and what comes next, see [DECISIONS.md](../DECISIONS.md). The original build plan is kept at the end, with notes on what changed.

## Goal

Turn "run a risk review" from a wall of numbered text into a structured, verifiable table inside the existing chat: severity, category, a short reason, the exact quote, and the page it came from. Lawyers can scan it, filter it, and check every finding against the source in one click.

## Flow

```
user: "Run a risk review of this document"
  -> agent reads the document and starts calling present_risks(risks[])     (PydanticAI tool)
       backend streams  status{reviewing}         -> frontend shows the table skeleton
  -> tool saves the risks as findings under a new review_id
       each finding's page is derived by locating its quote in the PDF text
  -> tool returns ToolReturn(
         return_value = {accepted, counts, top[3 titles]}   -> to the model
         metadata     = RiskTable (saved findings, IDs, pages) -> to the app, never the model)
       backend streams  risk_table{table}         -> frontend renders the table
  -> model writes a short summary
       backend streams  content* ... message ... done
  -> assistant message saved with parts=[{type:"risk_table", version:1, data:{review_id, counts}}]
```

On reload, `GET /api/conversations/{id}/messages` hydrates each stored part back into the full table from the `findings` table, so chat history, a refresh and the review page all render from the same saved rows.

## Backend

**`services/llm.py`**
- `agent`: Claude Haiku 5.5 via PydanticAI, with one tool, `present_risks`, and `ChatDeps` carrying a typed `save_review` function. The tool never touches the database itself, and the eval passes an in-memory fake.
- `build_prompt`: the document block, a prompt-cache point, then the chat history and the new message. The system prompt, tool definition and document are read from Anthropic's cache after the first request in a conversation. History isn't cached yet, because it's replayed as one text block.
- `chat_with_document`: turns PydanticAI's event stream into a typed union, `ChatEvent = TextChunk | ReviewStarted | RiskTable`. `ReviewStarted` fires when the model starts writing the tool call. `RiskTable` comes from the tool result's metadata. Thinking parts are never forwarded.
- Prompt injection: the system prompt says text inside `<document>` tags is data, never instructions, and `neutralise_document_tags` escapes any `<document>` tag inside the document text.

**`web/routers/messages.py`**: maps `ChatEvent`s onto server-sent events: `content`, `status`, `risk_table`, then `message` (the saved message, with its table hydrated) and `done`. Each event is a Pydantic model.

**`services/risk.py`**: the models: `RiskInput` (what the model sends; deliberately no page field), `FindingOut`, `RiskTable`, and the stored vs client message-part shapes (`StoredRiskTablePart` references a review; `RiskTablePart` carries the full table). Also `save_review`, `summarise_risks` and `hydrate_parts`.

**`services/quote.py`**: `locate_quote` normalises whitespace, hyphenated line breaks and quote marks, looks for the whole quote on each page, and falls back to the quote's first six words (stopping at a `...`). The match gives the page; no match gives no page and no link.

**`services/highlight.py`** and **`GET /api/findings/{id}/highlights`**: read the page's words with positions from the PDF, match the finding's quote word by word (ignoring punctuation, with the same opening-words fallback), and return one box per line as fractions of the page, so the viewer can draw them at any zoom.

**`services/reviews.py`**, **`GET /api/risk-reviews`** and **`GET /api/risk-reviews/{review_id}`**: the latest review of each document (filename, severity counts, age) and a single review with its document.

## Data model

- `messages.parts`: a JSON list of typed, versioned entries `{type, version, data}`. Text stays in `content`, so chat history is unchanged; parts carry rich output. A new kind of card is one new part type and one new component.
- `findings`: `id, review_id, conversation_id, document_id, position, title, severity, category, summary, quote, page, created_at`. `position` keeps display order. `page` is nullable and always derived in code. `review_id` is a generated ID, not a table: "the latest review of a document" is the newest `review_id` for that `document_id`. Findings are deleted with their conversation or document.

## Frontend

- `RiskTable.tsx`: `RiskTableCard` (severity chips that filter, worst first, expandable rows; the quote is a button that jumps to the document when the finding has a page) and `RiskTableSkeleton` (shown on `status`).
- `use-messages.ts`: handles `status`, `risk_table` and `message` alongside the streamed text.
- `DocumentViewer.tsx`: jumps to a finding's page and draws the highlight boxes over the PDF page.
- `RiskReviewList.tsx` and `RiskReviewPage.tsx`: the sidebar section and the full-page review view, reusing `RiskTableCard`.

## Quality and evidence

1. **Structured output**: the tool's Pydantic schema validates every risk.
2. **Pages come from the quote, not the model**: see `locate_quote`.
3. **Severity counts are computed in code**, never asked of the model.
4. **Measured with `evals/risk_eval.py`**: it runs the real agent and the app's own prompt over `sample-docs/` and records tool use, risks per review, whether each quote is found exactly or by its opening words, whether the summary's stated counts match the table, title stability across runs, time, and tokens (including cache reads and writes). Results are saved in `evals/results/` with the commit and a hash of the prompt files.

Results so far:
- **Quote wording**: telling the model in the tool schema to copy quotes character for character raised exact matches from 91% to 99% (10 runs per document).
- **Model choice**: Haiku 5.5 against the starter's Haiku 4.5, 5 runs per document: exact quotes 100% vs 97.5%, 11.5 vs 7.9 risks per review, 0.41¢ vs 1.72¢ per review, 20.2s vs 14.6s.
- **Prompt caching**: each review writes the document to the cache once (3–8K tokens) and reads it back after the tool call, about 12% cheaper per review at these sizes.
- `rapidfuzz` was tried on the saved quotes. It agreed with `locate_quote` on 127 of 129, but needed a low threshold (~70) for the opening-words cases and could accept a negated clause, so it was left out. It remains an option as a third fallback.

## Tests

Deliberately small; each was checked by breaking the code and confirming the matching test fails.
- Backend (`backend/tests/`, `uv run pytest`): `locate_quote` (a hyphenated line break, the opening-words fallback, a missing or empty quote), the highlight matcher (punctuation-insensitive matching, one scaled box per line) and `summarise_risks` (counts and worst-first order).
- Frontend (`just test-frontend`): `RiskTableCard` lists worst first, filters by severity and resets, jumps to the document from a located quote, and offers no jump for an unlocated one.
- Not covered yet: the SSE stream parser in `use-messages.ts` (it would need moving into a pure function first) and the API routes. Model quality is covered by the evals, not unit tests.

## Known trade-offs

- Findings are saved by the tool mid-stream, so a stream that fails afterwards can leave findings no message references. Harmless and invisible.
- An opening-words match proves where a quote starts, not that the rest is verbatim.
- JSON `parts` have no database-level constraints; Pydantic validation on write and read is the guard.
- Scanned PDFs have no extractable text, so quote location is impossible without OCR.
- The whole document goes into every request. That's fine at the sample sizes, and caching keeps repeat reads cheap, but long documents need a different approach (see DECISIONS.md).

## Planned improvement: cite paragraph IDs instead of quoting text

Today the model copies a quote and the backend searches for it. That's where drift comes from: in the early evals the unlocated quotes were all paraphrases of real text (reworded, merged, or missing a quotation mark). A deterministic alternative is to number the document's paragraphs at extraction (`[P12] ...`), have the model cite the ID, and let the backend look up that paragraph's exact text and page. No search, no paraphrase, and a cited ID is trivially checked for existence.
- **Wins:** exact quote and page by construction; no fuzzy matching; PyMuPDF text blocks carry positions, so the viewer could highlight the whole paragraph. Chat answers could cite `[P12]` too, and the same IDs would support search over long documents.
- **Costs:** needs paragraph segmentation (blocks can split or merge clauses; legal numbering like `4.2.1` may be a better boundary); the stored text format changes, so existing documents need re-extraction; slightly more prompt tokens; the model can still cite the wrong ID (existence is checkable, relevance is not); a whole paragraph can be long to show, so the row might show a short highlight validated as a substring of the paragraph.
- **How to judge it:** the eval would report the share of cited IDs that exist and, on a sample, whether the paragraph supports the claim.

## Original build plan

The feature was built in small stages, one commit each. Kept for history; notes in italics say what changed.

1. Risk models + stub `present_risks` tool; prompt trigger.
2. Tool-aware streaming in `llm.py` (typed events).
3. `messages.py` emits the table as its own SSE event. *Named `risk_table`, with a separate `status` event added later for the skeleton.*
4. `findings` table, `messages.parts`, migration, schemas, hydration.
5. Frontend plumbing: types, `use-messages.ts`.
6. `RiskTable` component (chips, expandable rows, filters).
7. Quality: `locate_quote` fills `Finding.page`.
8. Stretch items. *Built: progress skeleton, jump-to-page, quote highlighting, the Risk reviews section and page. Not built: a stronger-model validator, an `ask_user` question (buyer, tenant or lender), multi-document conversations.*
9. Tests, agreed one by one before writing.
10. Compare models with `evals/risk_eval.py`. *Done: switched to Haiku 5.5.*
11. `just check`, README / DECISIONS, Loom.

*The planned tool contract also had a `rejected[]` list so the model could retry bad quotes. It was dropped: every risk is saved, and a quote that can't be located simply gets no page.*
