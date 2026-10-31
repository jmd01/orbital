import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Loader2 } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/utils";
import type { Finding, RiskTable, Severity } from "../types";

const SEVERITY_STYLES: Record<
	Severity,
	{ label: string; chip: string; dot: string }
> = {
	high: { label: "High", chip: "bg-red-50 text-red-700", dot: "bg-red-500" },
	medium: {
		label: "Medium",
		chip: "bg-amber-50 text-amber-700",
		dot: "bg-amber-500",
	},
	low: {
		label: "Low",
		chip: "bg-neutral-100 text-neutral-600",
		dot: "bg-neutral-400",
	},
};

const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];

function SeverityChip({ severity }: { severity: Severity }) {
	const style = SEVERITY_STYLES[severity];
	return (
		<span
			className={cn(
				"inline-flex w-[4.5rem] flex-shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
				style.chip,
			)}
		>
			<span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
			{style.label}
		</span>
	);
}

interface FindingRowProps {
	finding: Finding;
	open: boolean;
	onToggle: () => void;
	onViewFinding: (finding: Finding) => void;
}

function FindingRow({
	finding,
	open,
	onToggle,
	onViewFinding,
}: FindingRowProps) {
	const page = finding.page;
	return (
		<li className="border-t border-neutral-100 first:border-t-0">
			<button
				type="button"
				onClick={onToggle}
				aria-expanded={open}
				className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-neutral-50"
			>
				<SeverityChip severity={finding.severity} />
				<span className="min-w-0 flex-1">
					<span className="block text-sm font-medium text-neutral-800">
						{finding.title}
					</span>
					<span className="block text-xs text-neutral-400">
						{finding.category}
					</span>
				</span>
				<ChevronDown
					className={cn(
						"mt-0.5 h-4 w-4 flex-shrink-0 text-neutral-400 transition-transform",
						open && "rotate-180",
					)}
				/>
			</button>
			<AnimatePresence initial={false}>
				{open && (
					<motion.div
						initial={{ height: 0, opacity: 0 }}
						animate={{ height: "auto", opacity: 1 }}
						exit={{ height: 0, opacity: 0 }}
						transition={{ duration: 0.18 }}
						className="overflow-hidden"
					>
						<div className="space-y-2.5 px-3 pb-3 pl-[5.75rem]">
							<p className="text-sm leading-relaxed text-neutral-600">
								{finding.summary}
							</p>
							{page !== null ? (
								<button
									type="button"
									onClick={() => onViewFinding(finding)}
									title="Show in the document"
									className="block w-full cursor-pointer rounded-r-sm border-l-2 border-neutral-300 pl-3 text-left font-serif text-[13px] italic leading-relaxed text-neutral-500 transition-colors hover:border-amber-300 hover:bg-amber-50 hover:text-neutral-700"
								>
									“{finding.quote}”
								</button>
							) : (
								<blockquote className="border-l-2 border-neutral-300 pl-3 font-serif text-[13px] italic leading-relaxed text-neutral-500">
									“{finding.quote}”
								</blockquote>
							)}
						</div>
					</motion.div>
				)}
			</AnimatePresence>
		</li>
	);
}

interface RiskTableCardProps {
	table: RiskTable;
	onViewFinding: (finding: Finding) => void;
}

export function RiskTableCard({ table, onViewFinding }: RiskTableCardProps) {
	const [openId, setOpenId] = useState<string | null>(null);
	const [filter, setFilter] = useState<Severity | null>(null);

	// Most serious first; sort is stable, so the model's order holds within a severity.
	const findings = [...table.findings]
		.sort(
			(a, b) =>
				SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity),
		)
		.filter((finding) => filter === null || finding.severity === filter);

	return (
		<div className="my-2 overflow-hidden rounded-xl border border-neutral-200 bg-white">
			<div className="flex items-center justify-between gap-2 border-b border-neutral-100 bg-neutral-50 px-3 py-2">
				<span className="text-xs font-medium text-neutral-500">
					{table.findings.length} risks
				</span>
				<div className="flex items-center gap-1.5">
					{SEVERITY_ORDER.filter((s) => table.counts[s] > 0).map((severity) => {
						const style = SEVERITY_STYLES[severity];
						const active = filter === severity;
						return (
							<button
								key={severity}
								type="button"
								aria-pressed={active}
								onClick={() => setFilter(active ? null : severity)}
								className={cn(
									"inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium transition",
									style.chip,
									active && "ring-1 ring-current",
									filter !== null && !active && "opacity-50",
								)}
							>
								<span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
								{style.label} {table.counts[severity]}
							</button>
						);
					})}
				</div>
			</div>
			<ul>
				{findings.map((finding) => (
					<FindingRow
						key={finding.id}
						finding={finding}
						open={openId === finding.id}
						onViewFinding={onViewFinding}
						onToggle={() =>
							setOpenId((current) =>
								current === finding.id ? null : finding.id,
							)
						}
					/>
				))}
			</ul>
		</div>
	);
}

const SKELETON_ROWS = [
	{ id: "a", title: "w-4/5" },
	{ id: "b", title: "w-3/5" },
	{ id: "c", title: "w-2/3" },
];

// Shown while the model is still writing out its findings, in the shape of the table to come.
export function RiskTableSkeleton() {
	return (
		<output className="my-2 block overflow-hidden rounded-xl border border-neutral-200 bg-white">
			<div className="flex items-center gap-2 border-b border-neutral-100 bg-neutral-50 px-3 py-2">
				<Loader2 className="h-3.5 w-3.5 animate-spin text-neutral-400" />
				<span className="text-xs font-medium text-neutral-500">
					Reviewing the document for risks…
				</span>
			</div>
			<ul>
				{SKELETON_ROWS.map((row) => (
					<li
						key={row.id}
						className="flex items-center gap-3 border-t border-neutral-100 px-3 py-3 first:border-t-0"
					>
						<span className="h-5 w-[4.5rem] flex-shrink-0 animate-pulse rounded-full bg-neutral-100" />
						<span
							className={cn(
								"h-3 animate-pulse rounded bg-neutral-100",
								row.title,
							)}
						/>
					</li>
				))}
			</ul>
		</output>
	);
}
