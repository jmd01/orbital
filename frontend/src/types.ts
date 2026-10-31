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

export interface ConversationDetail extends Conversation {
	document?: Document;
}
