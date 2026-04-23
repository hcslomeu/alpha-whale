"""Shared test doubles for AlphaWhale tests."""

from types import TracebackType
from typing import Literal


class FakeMetric:
    """Simple metric test double for record/add calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[float | int, dict | None]] = []

    def record(self, value: float, *, attributes: dict | None = None) -> None:
        self.calls.append((value, attributes))

    def add(self, value: int, *, attributes: dict | None = None) -> None:
        self.calls.append((value, attributes))


class FakeSpan:
    """Context manager that stores span attributes."""

    def __init__(self, name: str, attributes: dict[str, object]) -> None:
        self.name = name
        self.initial_attributes = attributes
        self.attributes: dict[str, object] = {}

    def __enter__(self) -> "FakeSpan":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        return False

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class FakeLogfire:
    """Minimal Logfire double for spans and metrics."""

    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []
        self.histograms: dict[str, FakeMetric] = {}
        self.counters: dict[str, FakeMetric] = {}

    def span(self, name: str, **attributes: object) -> FakeSpan:
        span = FakeSpan(name, attributes)
        self.spans.append(span)
        return span

    def metric_histogram(self, name: str, **_kwargs: object) -> FakeMetric:
        metric = self.histograms.setdefault(name, FakeMetric())
        return metric

    def metric_counter(self, name: str, **_kwargs: object) -> FakeMetric:
        metric = self.counters.setdefault(name, FakeMetric())
        return metric
