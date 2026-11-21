"""Service health: what each service reports, and what the board shows for all of them."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

SLOW_LATENCY_MS = 500  # an up service slower than this shows as degraded


class Status(StrEnum):
    """Health of one service, or of the whole board."""

    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"


_SEVERITY = {Status.UP: 0, Status.DEGRADED: 1, Status.DOWN: 2}


class InvalidServiceError(ValueError):
    """Raised when a service report is malformed."""


@dataclass(frozen=True)
class Service:
    """One service as last polled."""

    name: str
    status: Status
    latency_ms: int

    @property
    def shown_status(self) -> Status:
        """The status the board shows: an up service that answers slowly counts as degraded."""
        if self.status is Status.UP and self.latency_ms >= SLOW_LATENCY_MS:
            return Status.DEGRADED
        return self.status


def parse_service(raw: Mapping[str, object]) -> Service:
    """Build a service from a JSON report, rejecting anything the board cannot show."""
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        msg = f"service needs a non-empty name, got {name!r}"
        raise InvalidServiceError(msg)
    status = raw.get("status")
    if status not in set(Status):
        msg = f"service {name!r} has unknown status {status!r}"
        raise InvalidServiceError(msg)
    latency = raw.get("latency_ms", 0)
    if not isinstance(latency, int) or isinstance(latency, bool) or latency < 0:
        msg = f"service {name!r} has invalid latency {latency!r}"
        raise InvalidServiceError(msg)
    return Service(name, Status(str(status)), latency)


def overall(services: Iterable[Service]) -> Status:
    """The worst status any service shows; an empty board is up."""
    return max((s.shown_status for s in services), key=_SEVERITY.__getitem__, default=Status.UP)


def availability(history: Sequence[Status]) -> int:
    """Share of samples in which the service was not down; 1.0 with no samples."""
    if not history:
        return 1.0
    return sum(status is not Status.DOWN for status in history) / len(history)
