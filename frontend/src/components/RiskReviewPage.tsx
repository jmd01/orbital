import { Loader2, MessageSquare } from "lucide-react";
import { relativeTime } from "../lib/utils";
import type { Finding, ReviewDetail } from "../types";
import { RiskTableCard } from "./RiskTable";
import { Button } from "./ui/button";

interface RiskReviewPageProps {
	review: ReviewDetail | null;
	loading: boolean;
	error: string | null;
	onViewFinding: (finding: Finding) => void;
	onOpenConversation: (conversationId: string) => void;
}

// A whole risk review as the main panel; the document it was run on is in the reader beside it.
export function RiskReviewPage({
	review,
	loading,
	error,
	onViewFinding,
	onOpenConversation,
}: RiskReviewPageProps) {
	if (loading) {
		return (
			<div className="flex flex-1 items-center justify-center bg-white">
				<Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
			</div>
		);
	}

	if (error || !review) {
		return (
			<div className="flex flex-1 items-center justify-center bg-white px-6">
				<p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">
					{error ?? "Risk review not found"}
				</p>
			</div>
		);
	}

	return (
		<div className="flex min-w-0 flex-1 flex-col bg-white">
			<div className="flex items-center justify-between gap-3 border-b border-neutral-100 px-6 py-3">
				<div className="min-w-0">
					<p className="truncate text-sm font-semibold text-neutral-800">
						{review.document.filename}
					</p>
					<p className="text-xs text-neutral-400">
						Risk review · {relativeTime(review.created_at)}
					</p>
				</div>
				<Button
					variant="ghost"
					size="sm"
					className="flex-shrink-0 gap-1.5 text-neutral-500"
					onClick={() => onOpenConversation(review.conversation_id)}
				>
					<MessageSquare className="h-3.5 w-3.5" />
					Open conversation
				</Button>
			</div>

			<div className="flex-1 overflow-y-auto px-6 py-4">
				<div className="mx-auto max-w-3xl">
					<RiskTableCard table={review.table} onViewFinding={onViewFinding} />
				</div>
			</div>
		</div>
	);
}
