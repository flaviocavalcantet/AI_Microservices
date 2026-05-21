"""Placeholder workload runner.

Actual AI model execution is intentionally not implemented yet.
"""

from typing import Any, Dict

from ...application.ports.workload_runner import WorkloadRunner


class PlaceholderWorkloadRunner(WorkloadRunner):
    """Explicitly blocks model execution until real workloads are designed."""

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("AI workload execution is not implemented yet")
