"""
Dataset Profiling Service
==========================
Production-grade service for generating comprehensive statistical profiles of datasets.

Key Features:
- CSV and JSON input support
- Missing value detection and analysis
- Column type classification (numeric, categorical, datetime, mixed)
- Summary statistics per column type
- Outlier detection
- Correlation analysis (numeric columns)
- Framework-independent: uses only pandas (no Flask, pymongo, etc.)
- Lazy singleton loading to defer pandas import
- Comprehensive error handling

Design Principles:
- Stateless by convention – all inputs through method parameters
- Structured output via dataclasses for type safety
- Extensible: easy to add new statistics or column type detectors
- Memory-efficient: processes streaming data where possible
- Thread-safe: double-checked locking for singleton pattern
"""

from __future__ import annotations

import io
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# Singleton lock for lazy pandas import
_LOCK = threading.Lock()
_SERVICE_INSTANCE: Optional[DatasetProfilingService] = None

# Constants
_DEFAULT_SAMPLE_SIZE = 5  # Number of sample values to include per column
_NUMERIC_THRESHOLD = 0.8  # Threshold for numeric column detection
_DATETIME_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
]


# ─────────────────────────────────────────────────────────────────────────
# Structured Output
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NumericStats:
    """Statistics for numeric columns."""

    min: float
    max: float
    mean: float
    median: float
    std_dev: float
    q25: float
    q75: float
    count: int


@dataclass(frozen=True)
class CategoricalStats:
    """Statistics for categorical columns."""

    unique_count: int
    top_value: Any
    top_count: int
    top_percentage: float
    count: int


@dataclass(frozen=True)
class ColumnProfile:
    """Comprehensive profile for a single column."""

    name: str
    type: Literal["numeric", "categorical", "datetime", "mixed", "unknown"]
    total_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    duplicate_count: int
    sample_values: list[Any]
    numeric_stats: Optional[NumericStats] = None
    categorical_stats: Optional[CategoricalStats] = None
    has_outliers: bool = False
    outlier_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "type": self.type,
            "total_count": self.total_count,
            "null_count": self.null_count,
            "null_percentage": round(self.null_percentage, 4),
            "unique_count": self.unique_count,
            "duplicate_count": self.duplicate_count,
            "sample_values": [str(v) for v in self.sample_values],
            "has_outliers": self.has_outliers,
            "outlier_count": self.outlier_count,
        }

        if self.numeric_stats:
            result["numeric_stats"] = {
                "min": round(self.numeric_stats.min, 6),
                "max": round(self.numeric_stats.max, 6),
                "mean": round(self.numeric_stats.mean, 6),
                "median": round(self.numeric_stats.median, 6),
                "std_dev": round(self.numeric_stats.std_dev, 6),
                "q25": round(self.numeric_stats.q25, 6),
                "q75": round(self.numeric_stats.q75, 6),
                "count": self.numeric_stats.count,
            }

        if self.categorical_stats:
            result["categorical_stats"] = {
                "unique_count": self.categorical_stats.unique_count,
                "top_value": str(self.categorical_stats.top_value),
                "top_count": self.categorical_stats.top_count,
                "top_percentage": round(self.categorical_stats.top_percentage, 4),
                "count": self.categorical_stats.count,
            }

        return result


@dataclass(frozen=True)
class DatasetProfile:
    """Complete statistical profile of a dataset."""

    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    numeric_column_count: int
    categorical_column_count: int
    datetime_column_count: int
    mixed_column_count: int
    memory_usage_bytes: int
    processing_time_ms: float
    correlations: dict[tuple[str, str], float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "numeric_column_count": self.numeric_column_count,
            "categorical_column_count": self.categorical_column_count,
            "datetime_column_count": self.datetime_column_count,
            "mixed_column_count": self.mixed_column_count,
            "memory_usage_bytes": self.memory_usage_bytes,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "columns": [col.to_dict() for col in self.columns],
            "correlations": {
                f"{col1}_{col2}": round(corr, 6)
                for (col1, col2), corr in self.correlations.items()
            },
        }


# ─────────────────────────────────────────────────────────────────────────
# Service Exceptions
# ─────────────────────────────────────────────────────────────────────────

class DatasetProfilingError(Exception):
    """Base exception for dataset profiling errors."""

    pass


class DatasetProfilingImportError(DatasetProfilingError):
    """Raised when pandas is not available."""

    pass


class InvalidInputError(DatasetProfilingError):
    """Raised when input data is invalid."""

    pass


class ProfilingError(DatasetProfilingError):
    """Raised when profiling computation fails."""

    pass


# ─────────────────────────────────────────────────────────────────────────
# Main Service
# ─────────────────────────────────────────────────────────────────────────

class DatasetProfilingService:
    """
    Production-grade dataset profiling service.

    Usage (production - singleton):
        service = DatasetProfilingService.get_default()
        profile = service.profile_csv(csv_data)

    Usage (testing - injected):
        service = DatasetProfilingService()
        profile = service.profile_records([{"a": 1}, {"a": 2}])
    """

    def __init__(self) -> None:
        """Initialize the service (lazy pandas import on first use)."""
        self._pd = None

    def profile_csv(self, csv_data: str) -> DatasetProfile:
        """
        Profile a CSV string.

        Args:
            csv_data: CSV content as string.

        Returns:
            Complete DatasetProfile with all statistics.

        Raises:
            DatasetProfilingImportError: If pandas is not installed.
            InvalidInputError: If CSV is malformed or empty.
            ProfilingError: If computation fails.
        """
        self._ensure_pandas()

        if not csv_data or not csv_data.strip():
            raise InvalidInputError("CSV data cannot be empty")

        try:
            df = self._pd.read_csv(io.StringIO(csv_data))
        except Exception as exc:
            raise InvalidInputError(f"Failed to parse CSV: {exc}") from exc

        return self._profile_dataframe(df)

    def profile_records(
        self, records: list[dict[str, Any]], orient: str = "records"
    ) -> DatasetProfile:
        """
        Profile a list of records (JSON-like dicts).

        Args:
            records: List of record dictionaries.
            orient: pandas JSON orientation (default: 'records').

        Returns:
            Complete DatasetProfile with all statistics.

        Raises:
            DatasetProfilingImportError: If pandas is not installed.
            InvalidInputError: If records are invalid or empty.
            ProfilingError: If computation fails.
        """
        self._ensure_pandas()

        if not records:
            raise InvalidInputError("Records list cannot be empty")

        if not isinstance(records, list):
            raise InvalidInputError("Records must be a list of dictionaries")

        try:
            df = self._pd.DataFrame.from_records(records)
        except Exception as exc:
            raise InvalidInputError(f"Failed to convert records to DataFrame: {exc}") from exc

        return self._profile_dataframe(df)

    # ─────────────────────────────────────────────────────────────────────
    # Private
    # ─────────────────────────────────────────────────────────────────────

    def _ensure_pandas(self) -> None:
        """Lazy import pandas (avoid hard dependency at module level)."""
        if self._pd is not None:
            return

        try:
            import pandas as pd

            self._pd = pd
            logger.debug("pandas loaded successfully")
        except ImportError as exc:
            raise DatasetProfilingImportError(
                "pandas is required for dataset profiling. "
                "Install it with: pip install pandas"
            ) from exc

    def _profile_dataframe(self, df: Any) -> DatasetProfile:
        """Generate complete profile from a DataFrame."""
        t0 = time.perf_counter()

        try:
            # Profile each column
            columns = []
            numeric_cols = []
            categorical_cols = []
            datetime_cols = []
            mixed_cols = []

            for col_name in df.columns:
                profile = self._profile_column(df[col_name])
                columns.append(profile)

                if profile.type == "numeric":
                    numeric_cols.append(col_name)
                elif profile.type == "categorical":
                    categorical_cols.append(col_name)
                elif profile.type == "datetime":
                    datetime_cols.append(col_name)
                elif profile.type == "mixed":
                    mixed_cols.append(col_name)

            # Compute correlations for numeric columns
            correlations = self._compute_correlations(df, numeric_cols)

            latency_ms = (time.perf_counter() - t0) * 1000

            return DatasetProfile(
                row_count=len(df),
                column_count=len(df.columns),
                columns=columns,
                numeric_column_count=len(numeric_cols),
                categorical_column_count=len(categorical_cols),
                datetime_column_count=len(datetime_cols),
                mixed_column_count=len(mixed_cols),
                memory_usage_bytes=int(df.memory_usage(deep=True).sum()),
                processing_time_ms=latency_ms,
                correlations=correlations,
            )
        except Exception as exc:
            logger.exception("Failed to profile DataFrame")
            raise ProfilingError(f"Dataset profiling failed: {exc}") from exc

    def _profile_column(self, series: Any) -> ColumnProfile:
        """Generate profile for a single column."""
        col_name = series.name or "unknown"
        col_type = self._detect_column_type(series)
        total_count = len(series)
        null_count = series.isna().sum()
        non_null_series = series.dropna()
        non_null_count = len(non_null_series)
        unique_count = non_null_series.nunique()
        duplicate_count = non_null_count - unique_count

        # Sample values (non-null only)
        sample_size = min(_DEFAULT_SAMPLE_SIZE, len(non_null_series))
        sample_values = non_null_series.iloc[:sample_size].tolist() if sample_size > 0 else []

        # Compute type-specific stats
        numeric_stats = None
        categorical_stats = None
        outliers_detected = False
        outlier_count = 0

        if col_type == "numeric":
            numeric_stats, outliers_detected, outlier_count = self._compute_numeric_stats(
                series, non_null_series
            )

        if col_type == "categorical":
            categorical_stats = self._compute_categorical_stats(non_null_series, non_null_count)

        return ColumnProfile(
            name=col_name,
            type=col_type,
            total_count=total_count,
            null_count=null_count,
            null_percentage=(null_count / total_count * 100) if total_count > 0 else 0,
            unique_count=unique_count,
            duplicate_count=duplicate_count,
            sample_values=sample_values,
            numeric_stats=numeric_stats,
            categorical_stats=categorical_stats,
            has_outliers=outliers_detected,
            outlier_count=outlier_count,
        )

    def _detect_column_type(self, series: Any) -> str:
        """Detect the type of a column."""
        if len(series) == 0:
            return "unknown"

        non_null_series = series.dropna()
        if len(non_null_series) == 0:
            return "unknown"

        # Check if it's a datetime type
        if self._pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"

        # Check if it's numeric
        if self._pd.api.types.is_numeric_dtype(series):
            return "numeric"

        # Try to infer: check if most values can be converted to numeric
        numeric_count = 0
        for val in non_null_series.iloc[:min(100, len(non_null_series))]:
            try:
                float(val)
                numeric_count += 1
            except (ValueError, TypeError):
                pass

        if numeric_count / len(non_null_series) >= _NUMERIC_THRESHOLD:
            return "numeric"

        # Check for mixed types
        type_set = set(type(v).__name__ for v in non_null_series.iloc[:min(50, len(non_null_series))])
        if len(type_set) > 1:
            return "mixed"

        # Default to categorical
        return "categorical"

    def _compute_numeric_stats(
        self, series: Any, non_null_series: Any
    ) -> tuple[Optional[NumericStats], bool, int]:
        """Compute statistics for numeric column."""
        try:
            # Convert to numeric, coercing errors
            numeric_series = self._pd.to_numeric(non_null_series, errors="coerce")
            numeric_series = numeric_series.dropna()

            if len(numeric_series) == 0:
                return None, False, 0

            min_val = float(numeric_series.min())
            max_val = float(numeric_series.max())
            mean_val = float(numeric_series.mean())
            median_val = float(numeric_series.median())
            std_val = float(numeric_series.std()) if len(numeric_series) > 1 else 0.0
            q25_val = float(numeric_series.quantile(0.25))
            q75_val = float(numeric_series.quantile(0.75))

            # Detect outliers using IQR method
            iqr = q75_val - q25_val
            lower_bound = q25_val - 1.5 * iqr
            upper_bound = q75_val + 1.5 * iqr
            outliers = (numeric_series < lower_bound) | (numeric_series > upper_bound)
            outlier_count = int(outliers.sum())

            stats = NumericStats(
                min=min_val,
                max=max_val,
                mean=mean_val,
                median=median_val,
                std_dev=std_val,
                q25=q25_val,
                q75=q75_val,
                count=len(numeric_series),
            )

            return stats, outlier_count > 0, outlier_count
        except Exception as exc:
            logger.warning(f"Failed to compute numeric stats: {exc}")
            return None, False, 0

    def _compute_categorical_stats(self, non_null_series: Any, total_count: int) -> CategoricalStats:
        """Compute statistics for categorical column."""
        try:
            value_counts = non_null_series.value_counts()
            if len(value_counts) == 0:
                return CategoricalStats(
                    unique_count=0,
                    top_value=None,
                    top_count=0,
                    top_percentage=0.0,
                    count=0,
                )

            top_value = value_counts.index[0]
            top_count = int(value_counts.iloc[0])
            top_percentage = (top_count / total_count * 100) if total_count > 0 else 0.0

            return CategoricalStats(
                unique_count=len(value_counts),
                top_value=top_value,
                top_count=top_count,
                top_percentage=top_percentage,
                count=len(non_null_series),
            )
        except Exception as exc:
            logger.warning(f"Failed to compute categorical stats: {exc}")
            return CategoricalStats(
                unique_count=0, top_value=None, top_count=0, top_percentage=0.0, count=0
            )

    def _compute_correlations(
        self, df: Any, numeric_cols: list[str]
    ) -> dict[tuple[str, str], float]:
        """Compute Pearson correlations between numeric columns."""
        try:
            if len(numeric_cols) < 2:
                return {}

            numeric_df = df[numeric_cols].apply(self._pd.to_numeric, errors="coerce")
            correlations = {}

            for i, col1 in enumerate(numeric_cols):
                for col2 in numeric_cols[i + 1 :]:
                    try:
                        corr = float(numeric_df[col1].corr(numeric_df[col2]))
                        correlations[(col1, col2)] = corr
                    except Exception:
                        pass

            return correlations
        except Exception as exc:
            logger.warning(f"Failed to compute correlations: {exc}")
            return {}


# ─────────────────────────────────────────────────────────────────────────
# Singleton Access
# ─────────────────────────────────────────────────────────────────────────


def get_default_service() -> DatasetProfilingService:
    """
    Get or create the default singleton service instance.

    Thread-safe using double-checked locking.
    Lazy pandas import on first use.
    """
    global _SERVICE_INSTANCE

    if _SERVICE_INSTANCE is not None:
        return _SERVICE_INSTANCE

    with _LOCK:
        if _SERVICE_INSTANCE is None:
            _SERVICE_INSTANCE = DatasetProfilingService()
            logger.debug("Created DatasetProfilingService singleton")

        return _SERVICE_INSTANCE


__all__ = [
    "DatasetProfilingService",
    "DatasetProfile",
    "ColumnProfile",
    "NumericStats",
    "CategoricalStats",
    "DatasetProfilingError",
    "InvalidInputError",
    "ProfilingError",
    "get_default_service",
]
