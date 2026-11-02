# Part 1: Most significant technical achievement

**Gmail and Google Drive connectors for Genie's Legal Workflows agent**

## 1. The problem and its context

Genie is an AI legal assistant. Lawyers work with it by giving the agent documents and asking it to draft, review and answer questions. The trouble is that a lawyer's documents live in their inbox and their shared drive, not on their desktop. Our customers were regularly asking for Genie to be able to read and query their Drive and email inbox, and our usage analytics (Mixpanel) showed users pasting Google Drive URLs straight into the chat box. The agent could not read these links and rejected the request.

The brief I was given was loose: "add Gmail and Drive connectors". Competitor analysis showed that products which already supported an MCP connection were mostly doing the minimum: natural-language search and query, with the agent returning results as text or a basic table. There was no easy way to interact with the search results, or with the connector, outside of a natural-language UX. I thought there was a bigger opportunity in making email and Drive first-class parts of the product, not just a data pipe. I was responsible for the full design.

## 2. Complexity and constraints

**Rich UX needs.** I wanted an interactive results table, HTML email viewed inside Genie, an in-modal Drive preview, and one-click import with a choice of email body, attachment or both. That is a rigid, complex UI that an agent should not be generating.

**Agent speed.** My first approach had the agent return a structured list of results. It was slow, and it got slower as the number of rows grew: in my testing it took over a minute for just ten rows. Structured output also gets less reliable as the schema becomes richer.

**Context protection.** Email, especially HTML email, is bloated. Putting full emails or whole documents into the agent's context would be slow, expensive and noisy.

**Google's security gate.** Google requires a third-party security assessment (CASA) before a product can use restricted Gmail and Drive scopes. The assessment includes dependency audits and a recorded demo on a staging server. It was slow, mostly waiting on others, and outside my control.

**A small team.** I built the OAuth flow, the backend, the frontend and the agent behaviour myself.

## 3. My approach

**Competitor analysis.** I installed Google and other cloud storage connectors (e.g. Box, Dropbox, SharePoint, OneDrive) in Claude and ChatGPT to understand what they offered and where the gaps were. I also secured two design partners: an existing customer who was keen to have this feature in Genie, and another from our panel of legal advisors. Both told me how they use connectors in other products, where those fall short, and how they would like this to work.

**The agent writes a query, not the results.** I gave the agent a skill that teaches it to turn the user's request into a Google search query string, and nothing more. The agent returns that string, and a results card is rendered. The frontend and backend then talk directly, outside the agent, to run the query and return the results, and the frontend renders them. In my testing this returned results in under ten seconds.

This was a trade-off. It gave up some agent flexibility (the agent cannot reason over the full list of results) in exchange for speed, and for full control of a complex UI without depending on the model to produce a large structured response. It also means the agent only sees the documents or emails the user decides to import, which is a useful security side effect.

**Context stays small.** For documents, I reused an existing pattern. Importing a file gives the agent only a document ID, plus tools it already had to inspect, query and edit that document. For Gmail, the full HTML email is shown to the user inside the message but is not sent to the agent. Email HTML is untrusted, so it is rendered in a sandbox where it cannot run scripts or reach the rest of the app.

**A richer interface than the brief asked for.** Late in the build I added two things. The first is a live view of the inbox in the side panel (the "islands" UI next to the chat), so users can keep track of email without leaving Genie. The second, for Drive, is a virtual file system and file picker, available both in the chat and in the side panel.

**Alternatives I considered.** Structured agent output (built first, then dropped for speed). Importing everything into the conversation context (rejected on cost and noise). A bare connector with no custom UI (the minimum the brief asked for; I chose to go further).

**Validation.** I tested with both design partners while building. They raised concerns about trusting us with access to their data, which shaped how the connection flow is presented. Above all, they confirmed they want to reach their Drive and Gmail data from Genie.

## 4. Impact

The feature is about to go live, so I do not have usage numbers yet, but I expect it to have high impact:

- Searching Drive or Gmail now returns results in under ten seconds, where my first, structured-output approach took over a minute for ten rows. That is the difference between a feature lawyers will use and one they will abandon.
- There is clear existing demand. Many requests where users pasted a Drive URL were previously rejected, and those can now be served.
- The feature ships with Mixpanel events, so I will follow it closely after launch: who connects, how they use it, and whether Drive-link requests now succeed. I will also keep working with design partners to iterate and start to scope out V2.
- Success will be defined by whether customers connect Drive and Gmail to Genie, and whether they continue to use them.

## 5. Reflection

I underestimated how long the CASA assessment would take, and I would start it much sooner. The assessors want a working staging demo, so much of the build has to exist first, but I would still have begun the paperwork, the dependency clean-up and the process research in parallel with development instead of after it. A lot of the delay was learning what the process required and waiting for approvals.
