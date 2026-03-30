"""Data models for compliance audit results."""

from __future__ import annotations

from dataclasses import dataclass, field


def compute_grade(score: int) -> str:
    """Convert 0-100 percentage to letter grade."""
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


@dataclass
class Violation:
    file: str
    line: int | None = None
    message: str = ""
    fix_hint: str | None = None
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class CategoryResult:
    name: str
    label: str
    max_points: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def score(self) -> int:
        """max_points minus len(violations), capped at 0."""
        return max(0, self.max_points - len(self.violations))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "max_points": self.max_points,
            "score": self.score,
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclass
class AppReport:
    app: str
    categories: list[CategoryResult] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(c.score for c in self.categories)

    @property
    def max_score(self) -> int:
        return sum(c.max_points for c in self.categories)

    @property
    def grade(self) -> str:
        """Percentage-based grade: total_score / max_score * 100."""
        if self.max_score == 0:
            return "A+"
        pct = int(self.total_score / self.max_score * 100)
        return compute_grade(pct)

    @property
    def total_violations(self) -> int:
        return sum(len(c.violations) for c in self.categories)

    @property
    def auto_fixable_count(self) -> int:
        return sum(1 for c in self.categories for v in c.violations if v.auto_fixable)

    @property
    def needs_review_count(self) -> int:
        return self.total_violations - self.auto_fixable_count

    def to_dict(self) -> dict:
        return {
            "app": self.app,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "grade": self.grade,
            "total_violations": self.total_violations,
            "auto_fixable_count": self.auto_fixable_count,
            "needs_review_count": self.needs_review_count,
            "categories": [c.to_dict() for c in self.categories],
        }
