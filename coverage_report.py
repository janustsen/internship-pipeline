from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class SourceCoverage:
    source: str
    raw: int = 0
    kept: int = 0
    dropped: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def drop(self, reason: str, count: int = 1) -> None:
        self.dropped[reason] += count

    def keep(self, count: int = 1) -> None:
        self.kept += count

    @property
    def dropped_total(self) -> int:
        return sum(self.dropped.values())

    def assert_accounted(self) -> None:
        accounted = self.kept + self.dropped_total
        if accounted != self.raw:
            raise AssertionError(
                f"{self.source} silent drop: raw={self.raw} kept={self.kept} "
                f"dropped={self.dropped_total}"
            )

    def line(self) -> str:
        reasons = ", ".join(f"{key}={value}" for key, value in sorted(self.dropped.items()))
        if not reasons:
            reasons = "none=0"
        suffix = f" errors={len(self.errors)}" if self.errors else ""
        return (
            f"{self.source}: raw={self.raw} -> kept={self.kept} -> "
            f"dropped({reasons}){suffix}"
        )


class CoverageReport:
    def __init__(self) -> None:
        self._sources: dict[str, SourceCoverage] = {}

    def source(self, name: str) -> SourceCoverage:
        if name not in self._sources:
            self._sources[name] = SourceCoverage(name)
        return self._sources[name]

    def assert_no_silent_drops(self) -> None:
        for coverage in self._sources.values():
            coverage.assert_accounted()

    def lines(self) -> list[str]:
        return [self._sources[key].line() for key in sorted(self._sources)]

    def __iter__(self):
        return iter(self._sources.values())
