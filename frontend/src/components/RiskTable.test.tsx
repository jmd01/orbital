import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import type { Finding, RiskTable, Severity } from "../types";
import { RiskTableCard } from "./RiskTable";

function finding(
	id: string,
	title: string,
	severity: Severity,
	page: number | null = 1,
): Finding {
	return {
		id,
		title,
		severity,
		category: "Rent",
		summary: `Why ${title} matters.`,
		quote: `The clause behind ${title}.`,
		page,
	};
}

function table(findings: Finding[]): RiskTable {
	const counts: Record<Severity, number> = { high: 0, medium: 0, low: 0 };
	for (const f of findings) counts[f.severity] += 1;
	return { review_id: "r1", counts, findings };
}

// Given in the model's order, deliberately not worst first.
const LOW = finding("a", "repair wording", "low");
const HIGH = finding("b", "uncapped rent review", "high");
const MEDIUM = finding("c", "short break notice", "medium");

test("findings are listed worst first", () => {
	render(
		<RiskTableCard
			table={table([LOW, HIGH, MEDIUM])}
			onViewFinding={vi.fn()}
		/>,
	);

	const rows = screen.getAllByRole("listitem");

	expect(rows).toHaveLength(3);
	expect(rows[0]).toHaveTextContent(HIGH.title);
	expect(rows[1]).toHaveTextContent(MEDIUM.title);
	expect(rows[2]).toHaveTextContent(LOW.title);
});

test("a severity chip filters the rows, and clicking it again shows them all", async () => {
	const user = userEvent.setup();
	render(
		<RiskTableCard
			table={table([LOW, HIGH, MEDIUM])}
			onViewFinding={vi.fn()}
		/>,
	);
	const highChip = screen.getByRole("button", { name: "High 1" });

	await user.click(highChip);

	expect(highChip).toHaveAttribute("aria-pressed", "true");
	const rows = screen.getAllByRole("listitem");
	expect(rows).toHaveLength(1);
	expect(rows[0]).toHaveTextContent(HIGH.title);

	await user.click(highChip);

	expect(highChip).toHaveAttribute("aria-pressed", "false");
	expect(screen.getAllByRole("listitem")).toHaveLength(3);
});

test("expanding a row shows the quote, which jumps to the finding in the document", async () => {
	const user = userEvent.setup();
	const onViewFinding = vi.fn<(finding: Finding) => void>();
	render(<RiskTableCard table={table([HIGH])} onViewFinding={onViewFinding} />);
	expect(
		screen.queryByText(HIGH.quote, { exact: false }),
	).not.toBeInTheDocument();

	await user.click(
		screen.getByRole("button", { name: new RegExp(HIGH.title) }),
	);
	await user.click(
		screen.getByRole("button", { name: new RegExp(HIGH.quote) }),
	);

	expect(onViewFinding).toHaveBeenCalledExactlyOnceWith(HIGH);
});

test("a quote that could not be located in the document offers no jump", async () => {
	const user = userEvent.setup();
	const unlocated = finding("d", "unlocated covenant", "high", null);
	render(<RiskTableCard table={table([unlocated])} onViewFinding={vi.fn()} />);

	await user.click(
		screen.getByRole("button", { name: new RegExp(unlocated.title) }),
	);

	expect(
		screen.getByText(unlocated.quote, { exact: false }),
	).toBeInTheDocument();
	expect(
		screen.queryByRole("button", { name: new RegExp(unlocated.quote) }),
	).not.toBeInTheDocument();
});
