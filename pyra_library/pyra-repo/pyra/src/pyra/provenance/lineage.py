"""Lineage graph over ledger entries (architecture section 11).

Edges point from an artifact to its parents. ``verify`` reports, rather than hides:
* ``missing_parent``: a parent id that is not in the graph,
* ``status_downgrade``: an entry whose status is below one of its parents (impossible if every
  quantity was made through ``Quantity.derive``, so it signals a forged or hand-edited record),
* ``cycle``: parents form a loop (impossible with content-addressed ids unless forged).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from pyra.provenance.ledger import Ledger, LedgerEntry


class LineageCycleError(ValueError):
    """The recorded parents form a loop (only possible in a forged ledger)."""

    def __init__(self, ids: list[str]) -> None:
        super().__init__(f"lineage contains a cycle involving: {sorted(ids)}")
        self.ids = ids


@dataclass(frozen=True)
class LineageIssue:
    """One problem found by ``LineageGraph.verify``."""

    kind: str          # "missing_parent" | "status_downgrade" | "cycle"
    artifact_id: str
    detail: str


class LineageGraph:
    """Parent/child graph over ledger entries, with integrity checks."""

    def __init__(self, entries: Iterable[LedgerEntry]) -> None:
        self._entries: dict[str, LedgerEntry] = {}
        for e in entries:
            self._entries.setdefault(e.prov.artifact_id, e)

    @classmethod
    def from_ledger(cls, ledger: Ledger) -> LineageGraph:
        """Build the graph from every entry in ``ledger``."""
        return cls(ledger.entries())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, artifact_id: object) -> bool:
        return artifact_id in self._entries

    def _require(self, artifact_id: str) -> LedgerEntry:
        try:
            return self._entries[artifact_id]
        except KeyError:
            raise KeyError(f"unknown artifact id: {artifact_id}") from None

    def parents(self, artifact_id: str) -> tuple[str, ...]:
        """Direct parent ids of an artifact (KeyError if the id is unknown)."""
        return self._require(artifact_id).prov.parents

    def ancestors(self, artifact_id: str) -> set[str]:
        """Every artifact this one depends on, directly or indirectly."""
        self._require(artifact_id)
        seen: set[str] = set()
        stack = list(self.parents(artifact_id))
        while stack:
            current = stack.pop()
            if current in seen or current not in self._entries:
                continue
            seen.add(current)
            stack.extend(self._entries[current].prov.parents)
        return seen

    def descendants(self, artifact_id: str) -> set[str]:
        """Every artifact that depends on this one, directly or indirectly."""
        self._require(artifact_id)
        children: dict[str, list[str]] = {}
        for aid, e in self._entries.items():
            for p in e.prov.parents:
                children.setdefault(p, []).append(aid)
        seen: set[str] = set()
        stack = list(children.get(artifact_id, []))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(children.get(current, []))
        return seen

    def topological_order(self) -> list[str]:
        """Parents before children, ties in ledger order. Raises LineageCycleError on a loop."""
        indegree = {
            aid: sum(1 for p in e.prov.parents if p in self._entries)
            for aid, e in self._entries.items()
        }
        children: dict[str, list[str]] = {}
        for aid, e in self._entries.items():
            for p in e.prov.parents:
                if p in self._entries:
                    children.setdefault(p, []).append(aid)
        queue = deque(aid for aid, n in indegree.items() if n == 0)
        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for child in children.get(current, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(order) != len(self._entries):
            raise LineageCycleError([aid for aid in self._entries if aid not in set(order)])
        return order

    def verify(self) -> list[LineageIssue]:
        """Integrity problems found in the graph; an empty list means none were found."""
        issues: list[LineageIssue] = []
        for aid, e in self._entries.items():
            for p in e.prov.parents:
                parent = self._entries.get(p)
                if parent is None:
                    issues.append(LineageIssue("missing_parent", aid, f"parent {p} not recorded"))
                elif e.status < parent.status:
                    issues.append(
                        LineageIssue(
                            "status_downgrade",
                            aid,
                            f"{e.status.name} is below parent {p} ({parent.status.name})",
                        )
                    )
        try:
            self.topological_order()
        except LineageCycleError as exc:
            issues.append(LineageIssue("cycle", exc.ids[0], str(exc)))
        return issues
