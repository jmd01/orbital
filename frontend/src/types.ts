export interface Conversation {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
	has_document: boolean;
}

export type Severity = "high" | "medium" | "low";

export interface Finding {
	id: string;
	title: string;
	severity: Severity;
	category: string;
	summary: string;
	quote: string;
	page: number | null;
}

export interface RiskTable {
	review_id: string;
	counts: Record<Severity, number>;
	findings: Finding[];
}

export interface RiskTablePart {
	type: "risk_table";
	version: 1;
	data: RiskTable;
}

// Rich output attached to a message. Add a member per new kind of part.
export type MessagePart = RiskTablePart;

export interface Message {
	id: string;
	conversation_id: string;
	role: "user" | "assistant" | "system";
	content: string;
	sources_cited: number;
	parts: MessagePart[];
	created_at: string;
}

// Server-sent events on the message stream, discriminated by `type`.
export type StreamEvent =
	| { type: "content"; content: string }
	| { type: "status"; status: "reviewing" }
	| { type: "risk_table"; table: RiskTable }
	| { type: "message"; message: Message }
	| { type: "done"; sources_cited: number; message_id: string };

export interface Document {
	id: string;
	conversation_id: string;
	filename: string;
	page_count: number;
	uploaded_at: string;
}

// A request to show a finding on its page of a document. The nonce makes repeat requests for the same page
// count as new ones, e.g. after the reader has paged away.
export interface PageJump {
	documentId: string;
	page: number;
	findingId: string; // whose quote to highlight on that page
	nonce: number;
}

// A rectangle on a page as fractions of its size, so it scales to any rendered width.
export interface HighlightBox {
	x0: number;
	y0: number;
	x1: number;
	y1: number;
}

// One entry in the Risk reviews list: the latest review of a document.
export interface ReviewSummary {
	review_id: string;
	conversation_id: string;
	document_id: string;
	document_filename: string;
	created_at: string;
	counts: Record<Severity, number>;
	total: number;
}

// A whole review with the document it was run on.
export interface ReviewDetail {
	conversation_id: string;
	created_at: string;
	document: Document;
	table: RiskTable;
}

export interface ConversationDetail extends Conversation {
	document?: Document;
}
