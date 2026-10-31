import { ShieldAlert } from "lucide-react";
import { cn, relativeTime } from "../lib/utils";
import type { ReviewSummary } from "../types";
import { SEVERITY_ORDER, SEVERITY_STYLES } from "./RiskTable";

interface RiskReviewListProps {
	reviews: ReviewSummary[];
	selectedReviewId: string | null;
	onSelect: (reviewId: string) => void;
}

// The latest risk review of each document, shown under the chat list.
export function RiskReviewList({
	reviews,
	selectedReviewId,
	onSelect,
}: RiskReviewListProps) {
	return (
		<div className="flex max-h-[40%] flex-shrink-0 flex-col border-t border-neutral-200">
			<div className="flex items-center gap-2 px-3 pt-3 pb-1">
				<ShieldAlert className="h-3.5 w-3.5 text-neutral-400" />
				<span className="text-sm font-semibold text-neutral-700">
					Risk reviews
				</span>
			</div>
			<div className="overflow-y-auto p-2 pt-1">
				{reviews.length === 0 ? (
					<p className="px-2 py-4 text-center text-xs text-neutral-400">
						Run a risk review in a chat and it appears here
					</p>
				) : (
					reviews.map((review) => (
						<button
							key={review.review_id}
							type="button"
							onClick={() => onSelect(review.review_id)}
							className={cn(
								"block w-full rounded-lg px-3 py-2.5 text-left transition-colors",
								selectedReviewId === review.review_id
									? "bg-neutral-100"
									: "hover:bg-neutral-50",
							)}
						>
							<p className="truncate text-sm font-medium text-neutral-800">
								{review.document_filename}
							</p>
							<p className="mt-0.5 flex items-center gap-2 text-xs text-neutral-400">
								{SEVERITY_ORDER.filter((s) => review.counts[s] > 0).map((s) => (
									<span key={s} className="inline-flex items-center gap-1">
										<span
											className={cn(
												"h-1.5 w-1.5 rounded-full",
												SEVERITY_STYLES[s].dot,
											)}
										/>
										{review.counts[s]}
									</span>
								))}
								<span>{relativeTime(review.created_at)}</span>
							</p>
						</button>
					))
				)}
			</div>
		</div>
	);
}
