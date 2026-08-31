"""Metrics stores: offline JSONL default and opt-in Opik backend (Chapter 15.3).

Single responsibility: persist evaluation events. The Opik backend mirrors
Chapter 4's OpikTracer pattern: it activates only when `opik_enabled` is true
and an API key is present, otherwise `is_active` returns False and writes are
skipped. Constraints: the offline default path must work with no environment
variables and no network; a missing optional key degrades to the offline
store, never an error.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from day2ops.config import Settings

OPIK_PROJECT_NAME = "day2-agentic-cicd"


class MetricsStore(ABC):
    """Interface for telemetry sinks."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """True when writes are actually persisted."""

    @abstractmethod
    def record(self, event: dict[str, object]) -> None:
        """Persist one event. Inactive stores skip the write silently."""


class JsonlStore(MetricsStore):
    """Default offline backend: one JSON object per line, append-only."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def is_active(self) -> bool:
        return True

    def record(self, event: dict[str, object]) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")


class OpikStore(MetricsStore):
    """Opt-in backend mirroring Chapter 4's OpikTracer.

    Activates only when `day2ops_OPIK_ENABLED` is true and
    `day2ops_OPIK_API_KEY` is set. Without both, `is_active` is False and
    `record` is a no-op, so the default offline path never touches the network.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._client: object | None = None

    @property
    def is_active(self) -> bool:
        return bool(self._settings.opik_enabled and self._settings.opik_api_key)

    def record(self, event: dict[str, object]) -> None:
        if not self.is_active:
            return
        if self._client is None:
            import opik

            self._client = opik.Opik(project_name=OPIK_PROJECT_NAME)
        getattr(self._client, "log_trace")(**event)


def default_store(path: Path | None = None) -> MetricsStore:
    """Return the configured store: Opik when opted in, JSONL otherwise."""
    settings = Settings()
    opik_store = OpikStore(settings)
    if opik_store.is_active:
        return opik_store
    return JsonlStore(path or Path("reports/telemetry.jsonl"))
