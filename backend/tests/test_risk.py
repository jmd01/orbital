from __future__ import annotations

from takehome.services.risk import RiskInput, Severity, summarise_risks


def risk(title: str, severity: Severity) -> RiskInput:
    return RiskInput(title=title, severity=severity, category="c", summary="s", quote="q")


def test_summary_counts_by_severity_and_lists_the_worst_risks_first() -> None:
    risks = [
        risk("low one", "low"),
        risk("high one", "high"),
        risk("medium one", "medium"),
        risk("high two", "high"),
        risk("medium two", "medium"),
    ]

    result = summarise_risks(risks)

    assert result.accepted == 5
    assert result.counts == {"high": 2, "medium": 2, "low": 1}
    # Worst first, original order within a severity, capped at three.
    assert result.top == ["high one", "high two", "medium one"]
