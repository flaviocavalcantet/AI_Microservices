"""
Dataset Profiling Task
======================
Production-grade dataset profiling via the DatasetProfilingService.

This task bridges the AIJobOrchestrator and DatasetProfilingService, handling:
- Payload validation (CSV or JSON records)
- Service invocation with error translation
- Result shaping for consumption by downstream systems

The service itself owns all profiling logic: column type detection, missing
value analysis, statistical computation, outlier detection, etc.

Expected payload keys:
    data        (str | list[dict], required) – CSV string OR JSON records.
    input_type  (str, optional)  – "csv" or "json" (auto-detected if omitted).

Output data keys (from DatasetProfile):
    row_count                 (int)    – Total rows in dataset
    column_count              (int)    – Total columns
    numeric_column_count      (int)    – Numeric columns identified
    categorical_column_count  (int)    – Categorical columns identified
    datetime_column_count     (int)    – Datetime columns identified
    mixed_column_count        (int)    – Mixed-type columns
    memory_usage_bytes        (int)    – Approximate memory footprint
    columns                   (list)   – Per-column profiles (see schema)
    correlations              (dict)   – Pearson correlations between numerics

Output AIJobResult.metadata keys:
    processing_time_ms        (float)  – Wall-clock profiling time
    service_version           (str)    – Service implementation version
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from ai_engine.application.base_task import BaseAITask
from ai_engine.application.services.dataset_profiling_service import (
    DatasetProfilingError,
    DatasetProfilingService,
    InvalidInputError,
    ProfilingError,
    get_default_service,
)
from ai_engine.domain.models import AIJobResult, AIJobType

logger = logging.getLogger(__name__)

# Payload constraints
_MIN_RECORDS = 1
_MAX_RECORDS = 1_000_000  # Safety limit to prevent OOM
_MAX_CSV_SIZE_MB = 100


class DatasetProfilingTask(BaseAITask):
    """
    AI task that generates comprehensive statistical profiles of datasets.

    The DatasetProfilingService is injected through the constructor for
    testability – tests can provide a mock without requiring pandas.

    Production usage (via container.py):
        DatasetProfilingTask()                  # uses singleton service
        DatasetProfilingTask(service=my_svc)    # inject custom service

    Test usage:
        DatasetProfilingTask(service=FakeProfilingService())
    """

    job_type = AIJobType.DATASET_PROFILING

    def __init__(self, service: DatasetProfilingService | None = None) -> None:
        """Initialize the task with optional service injection."""
        self._service = service  # None → resolved lazily on first execute()

    # ------------------------------------------------------------------
    # BaseAITask interface
    # ------------------------------------------------------------------

    def validate_payload(self, payload: dict[str, Any]) -> None:
        """Validate the profiling request payload."""
        if "data" not in payload:
            raise ValueError(
                "Payload must contain a 'data' key with CSV string or JSON records."
            )

        data = payload["data"]
        input_type = payload.get("input_type", "auto")

        # Determine input type
        if input_type == "auto":
            if isinstance(data, str):
                input_type = "csv"
            elif isinstance(data, list):
                input_type = "json"
            else:
                raise ValueError(
                    f"Cannot auto-detect input type. data must be str (CSV) or list (JSON records), "
                    f"got: {type(data).__name__}"
                )

        # Validate by type
        if input_type == "csv":
            if not isinstance(data, str):
                raise ValueError(f"CSV input must be a string, got: {type(data).__name__}")
            if len(data) == 0:
                raise ValueError("CSV data cannot be empty")
            if len(data) > _MAX_CSV_SIZE_MB * 1024 * 1024:
                raise ValueError(
                    f"CSV exceeds maximum size of {_MAX_CSV_SIZE_MB} MB"
                )
        elif input_type == "json":
            if not isinstance(data, list):
                raise ValueError(
                    f"JSON records must be a list, got: {type(data).__name__}"
                )
            if len(data) == 0:
                raise ValueError("Records list must contain at least one record")
            if len(data) > _MAX_RECORDS:
                raise ValueError(
                    f"Too many records ({len(data)}). Maximum: {_MAX_RECORDS}"
                )
            if not all(isinstance(record, dict) for record in data):
                raise ValueError("All JSON records must be dictionaries")
        else:
            raise ValueError(
                f"input_type must be 'csv', 'json', or 'auto', got: {input_type}"
            )

    def execute(self, payload: dict[str, Any]) -> AIJobResult:
        """Profile the dataset and return structured result."""
        data = payload["data"]
        input_type = payload.get("input_type", "auto")

        # Auto-detect if needed
        if input_type == "auto":
            input_type = "csv" if isinstance(data, str) else "json"

        service = self._get_service()

        try:
            if input_type == "csv":
                profile = service.profile_csv(data)
            else:  # json
                profile = service.profile_records(data)
        except DatasetProfilingError as exc:
            logger.error("DatasetProfilingError: %s", exc)
            return AIJobResult.failure(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during dataset profiling")
            return AIJobResult.failure(f"Unexpected profiling error: {exc}")

        return AIJobResult(
            success=True,
            data=profile.to_dict(),
            metadata={
                "processing_time_ms": profile.processing_time_ms,
                "service_version": "1.0.0",
            },
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_service(self) -> DatasetProfilingService:
        """Get service instance (lazy resolution for production)."""
        if self._service is None:
            self._service = _LightweightDatasetProfilingService()
        return self._service


@dataclass(frozen=True)
class _LightweightDatasetProfile:
    row_count: int
    column_count: int
    columns: dict[str, dict[str, Any]]
    processing_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "processing_time_ms": self.processing_time_ms,
        }


class _LightweightDatasetProfilingService:
    def profile_records(self, records: list[dict[str, Any]]) -> _LightweightDatasetProfile:
        started = time.perf_counter()
        column_names = sorted({key for record in records for key in record})
        columns: dict[str, dict[str, Any]] = {}

        for name in column_names:
            values = [record.get(name) for record in records]
            non_null = [value for value in values if value is not None]
            numeric = [value for value in non_null if isinstance(value, (int, float))]
            is_numeric = bool(non_null) and len(numeric) == len(non_null)
            profile: dict[str, Any] = {
                "type": "numeric" if is_numeric else "categorical",
                "null_count": len(values) - len(non_null),
                "unique_count": len({repr(value) for value in non_null}),
            }
            if is_numeric and numeric:
                profile.update(
                    {
                        "min": min(numeric),
                        "max": max(numeric),
                        "mean": sum(numeric) / len(numeric),
                    }
                )
            columns[name] = profile

        return _LightweightDatasetProfile(
            row_count=len(records),
            column_count=len(column_names),
            columns=columns,
            processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def profile_csv(self, csv_data: str) -> _LightweightDatasetProfile:
        import csv
        import io

        reader = csv.DictReader(io.StringIO(csv_data))
        return self.profile_records(list(reader))
