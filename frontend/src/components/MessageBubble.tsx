import { motion } from "framer-motion";
import { Streamdown } from "streamdown";
import "streamdown/styles.css";
import { cn } from "../lib/utils";
import type { Finding, Message, RiskTable } from "../types";
import { RiskTableCard, RiskTableSkeleton } from "./RiskTable";

interface MessageBubbleProps {
	message: Message;
	onViewFinding: (finding: Finding) => void;
}

export function MessageBubble({ message, onViewFinding }: MessageBubbleProps) {
	if (message.role === "system") {
		return (
			<motion.div
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ duration: 0.2 }}
				className="flex justify-center py-2"
			>
				<p className="text-xs text-neutral-400">{message.content}</p>
			</motion.div>
		);
	}

	if (message.role === "user") {
		return (
			<motion.div
				initial={{ opacity: 0, y: 8 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.2 }}
				className="flex justify-end py-1.5"
			>
				<div className="max-w-[75%] rounded-2xl rounded-br-md bg-neutral-100 px-4 py-2.5">
					<p className="whitespace-pre-wrap text-sm text-neutral-800">
						{message.content}
					</p>
				</div>
			</motion.div>
		);
	}

	// Assistant message
	return (
		<motion.div
			initial={{ opacity: 0, y: 8 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.2 }}
			className="py-1.5"
		>
			<div
				className={cn("min-w-0", message.parts.length === 0 && "max-w-[80%]")}
			>
				{message.parts.map((part) => (
					<RiskTableCard
						key={part.data.review_id}
						table={part.data}
						onViewFinding={onViewFinding}
					/>
				))}
				<div className="prose">
					<Streamdown>{message.content}</Streamdown>
				</div>
				{message.sources_cited > 0 && (
					<p className="mt-1.5 text-xs text-neutral-400">
						{message.sources_cited} source
						{message.sources_cited !== 1 ? "s" : ""} cited
					</p>
				)}
			</div>
		</motion.div>
	);
}

interface StreamingBubbleProps {
	content: string;
	riskTable: RiskTable | null;
	reviewing: boolean;
	onViewFinding: (finding: Finding) => void;
}

export function StreamingBubble({
	content,
	riskTable,
	reviewing,
	onViewFinding,
}: StreamingBubbleProps) {
	return (
		<div className="py-1.5">
			<div
				className={cn("min-w-0", !(riskTable || reviewing) && "max-w-[80%]")}
			>
				{riskTable ? (
					<RiskTableCard table={riskTable} onViewFinding={onViewFinding} />
				) : (
					reviewing && <RiskTableSkeleton />
				)}
				{content ? (
					<div className="prose">
						<Streamdown mode="streaming">{content}</Streamdown>
					</div>
				) : !reviewing ? (
					<div className="flex items-center gap-1 py-2">
						<span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400" />
						<span
							className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400"
							style={{ animationDelay: "0.15s" }}
						/>
						<span
							className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400"
							style={{ animationDelay: "0.3s" }}
						/>
					</div>
				) : null}
				<span className="inline-block h-4 w-0.5 animate-pulse bg-neutral-400" />
			</div>
		</div>
	);
}
