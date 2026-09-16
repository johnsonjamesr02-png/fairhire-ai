"""
bias_audit.py

Implements the statistical fairness test that NYC Local Law 144 requires
for Automated Employment Decision Tools (AEDTs), which is built on the
EEOC's long-standing "four-fifths rule" (29 CFR 1607.4(D)):

    A selection rate for any group that is less than 80% (four-fifths) of
    the rate for the highest-scoring group indicates possible adverse
    impact and should be investigated.

This module is pure Python / pandas — no LLM calls — so it's deterministic,
unit-testable, and auditable on its own, independent of whatever scoring
model produced the candidate scores.

Reference: NYC Local Law 144 (Automated Employment Decision Tools),
EEOC Uniform Guidelines on Employee Selection Procedures, 29 CFR 1607.4(D).
"""

from dataclasses import dataclass, field
from typing import Iterable


FOUR_FIFTHS_THRESHOLD = 0.8


@dataclass
class GroupResult:
    group: str
    total: int
    selected: int

    @property
    def selection_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.selected / self.total


@dataclass
class BiasAuditReport:
    groups: list[GroupResult]
    reference_group: str
    reference_rate: float
    impact_ratios: dict[str, float] = field(default_factory=dict)
    flagged_groups: list[str] = field(default_factory=list)

    @property
    def passes_four_fifths_rule(self) -> bool:
        return len(self.flagged_groups) == 0

    def to_dict(self) -> dict:
        return {
            "reference_group": self.reference_group,
            "reference_selection_rate": round(self.reference_rate, 4),
            "groups": [
                {
                    "group": g.group,
                    "total_candidates": g.total,
                    "selected": g.selected,
                    "selection_rate": round(g.selection_rate, 4),
                    "impact_ratio": round(self.impact_ratios[g.group], 4),
                    "flagged": g.group in self.flagged_groups,
                }
                for g in self.groups
            ],
            "passes_four_fifths_rule": self.passes_four_fifths_rule,
            "flagged_groups": self.flagged_groups,
        }


def run_four_fifths_audit(
    candidates: Iterable[dict],
    group_field: str = "demographic_group",
    selected_field: str = "selected",
) -> BiasAuditReport:
    """
    candidates: iterable of dicts, each representing one scored/decided
        candidate, e.g. {"demographic_group": "Group A", "selected": True}.
        `selected` should already reflect whatever cutoff the hiring tool
        used (e.g. top-N fit score, or fit score >= threshold).

    Returns a BiasAuditReport with per-group selection rates, impact ratios
    relative to the highest-selection-rate group, and which groups (if any)
    fall below the four-fifths (80%) threshold.
    """
    totals: dict[str, int] = {}
    selected_counts: dict[str, int] = {}

    for c in candidates:
        group = c[group_field]
        totals[group] = totals.get(group, 0) + 1
        if c[selected_field]:
            selected_counts[group] = selected_counts.get(group, 0) + 1

    groups = [
        GroupResult(group=g, total=totals[g], selected=selected_counts.get(g, 0))
        for g in totals
    ]

    if not groups:
        raise ValueError("No candidates supplied to bias audit.")

    reference = max(groups, key=lambda g: g.selection_rate)
    reference_rate = reference.selection_rate

    impact_ratios = {}
    flagged = []
    for g in groups:
        ratio = 1.0 if reference_rate == 0 else g.selection_rate / reference_rate
        impact_ratios[g.group] = ratio
        if ratio < FOUR_FIFTHS_THRESHOLD:
            flagged.append(g.group)

    return BiasAuditReport(
        groups=groups,
        reference_group=reference.group,
        reference_rate=reference_rate,
        impact_ratios=impact_ratios,
        flagged_groups=flagged,
    )


if __name__ == "__main__":
    # quick manual sanity check
    demo_candidates = [
        {"demographic_group": "Group A", "selected": True},
        {"demographic_group": "Group A", "selected": True},
        {"demographic_group": "Group A", "selected": False},
        {"demographic_group": "Group A", "selected": True},
        {"demographic_group": "Group B", "selected": True},
        {"demographic_group": "Group B", "selected": False},
        {"demographic_group": "Group B", "selected": False},
        {"demographic_group": "Group B", "selected": False},
    ]
    report = run_four_fifths_audit(demo_candidates)
    import json
    print(json.dumps(report.to_dict(), indent=2))
