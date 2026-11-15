"""A small safety check for evidence references in lesson snippets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LessonCheck:
    ok: bool
    issues: tuple[str, ...]


def check_lesson(
    *, title: str, evidence_ids: tuple[str, ...] = (), concept_sketch: bool = False
) -> LessonCheck:
    """Require a lesson to cite evidence or be explicitly marked as a concept sketch."""
    issues: list[str] = []
    if not title.strip():
        issues.append("lesson title is required")
    if not evidence_ids and not concept_sketch:
        issues.append("add an evidence ID or mark this activity as a concept sketch")
    if any(not evidence_id.strip() for evidence_id in evidence_ids):
        issues.append("evidence IDs must not be empty")
    return LessonCheck(ok=not issues, issues=tuple(issues))


__all__ = ["LessonCheck", "check_lesson"]
