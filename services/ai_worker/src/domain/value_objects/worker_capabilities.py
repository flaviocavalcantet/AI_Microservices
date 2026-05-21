"""Worker capability value objects."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GPUCapabilities:
    """GPU availability summary."""

    available: bool
    count: int = 0
    provider: str = "unknown"
    details: dict | None = None


@dataclass(frozen=True)
class RAMCapabilities:
    """RAM availability summary."""

    total_bytes: int | None
    available_bytes: int | None


@dataclass(frozen=True)
class WorkerCapabilities:
    """Combined resource profile for scheduling future AI workloads."""

    gpu: GPUCapabilities
    ram: RAMCapabilities

    def to_dict(self) -> dict:
        return asdict(self)
