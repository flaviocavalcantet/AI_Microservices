# Dataset Profiling: Testing Guide & Recommendations

## Overview

This guide provides comprehensive testing strategies, fixtures, test cases, and best practices for the Dataset Profiling service.

## Architecture for Testability

The service design prioritizes testability:

```
┌─────────────────────────────────┐
│  DatasetProfilingTask           │  ← Thin orchestration layer (easy to test)
│  (Application Layer)            │
├─────────────────────────────────┤
│  DatasetProfilingService        │  ← Core logic (injectable, testable)
│  (Domain Logic)                 │
└─────────────────────────────────┘
     ↓ (dependency injection)
  FakeProfilingService (for tests)
```

**Key principle**: Dependencies are injected, allowing tests to mock the service without requiring pandas or real computations.

---

## Testing Levels

### 1. Unit Tests (Task Layer)

**Scope**: Test `DatasetProfilingTask` in isolation.

**Benefits**:
- No pandas dependency
- Fast execution (<100ms)
- Test payload validation logic
- Test error handling

**Test file**: `tests/unit/test_dataset_profiling_task.py`

```python
import pytest
from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
from ai_engine.domain.models import AIJobResult

# Mock the service
class FakeProfilingService:
    def profile_csv(self, csv_data):
        from ai_engine.application.services.dataset_profiling_service import (
            DatasetProfile, ColumnProfile
        )
        return DatasetProfile(
            row_count=2,
            column_count=2,
            columns=[],
            numeric_column_count=1,
            categorical_column_count=1,
            datetime_column_count=0,
            mixed_column_count=0,
            memory_usage_bytes=1024,
            processing_time_ms=10.5,
        )

    def profile_records(self, records):
        return self.profile_csv("")

# ─────────────────────────────────────────────────────────────────────────
# VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────

class TestDatasetProfilingTaskValidation:
    """Test payload validation without service execution."""

    def test_missing_data_key(self):
        """Should reject payload without 'data' key."""
        task = DatasetProfilingTask(service=FakeProfilingService())
        with pytest.raises(ValueError, match="'data' key"):
            task.validate_payload({"records": []})

    def test_csv_empty_string(self):
        """Should reject empty CSV."""
        task = DatasetProfilingTask()
        with pytest.raises(ValueError, match="CSV data cannot be empty"):
            task.validate_payload({"data": ""})

    def test_csv_exceeds_size(self):
        """Should reject CSV exceeding 100 MB."""
        task = DatasetProfilingTask()
        large_csv = "x" * (101 * 1024 * 1024)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            task.validate_payload({"data": large_csv})

    def test_json_not_list(self):
        """Should reject JSON that is not a list."""
        task = DatasetProfilingTask()
        with pytest.raises(ValueError, match="must be a list"):
            task.validate_payload({"data": {"a": 1}})

    def test_json_empty_list(self):
        """Should reject empty JSON records."""
        task = DatasetProfilingTask()
        with pytest.raises(ValueError, match="cannot be empty"):
            task.validate_payload({"data": []})

    def test_json_too_many_records(self):
        """Should reject >1M records."""
        task = DatasetProfilingTask()
        records = [{"a": i} for i in range(1_000_001)]
        with pytest.raises(ValueError, match="Too many records"):
            task.validate_payload({"data": records})

    def test_json_not_all_dicts(self):
        """Should reject JSON with non-dict records."""
        task = DatasetProfilingTask()
        with pytest.raises(ValueError, match="must be dictionaries"):
            task.validate_payload({"data": [{"a": 1}, "not_a_dict"]})

    def test_invalid_input_type(self):
        """Should reject unknown input_type."""
        task = DatasetProfilingTask()
        with pytest.raises(ValueError, match="'auto'"):
            task.validate_payload({
                "data": "col1,col2\n1,2",
                "input_type": "invalid"
            })

    def test_auto_detect_csv(self):
        """Should auto-detect CSV input."""
        task = DatasetProfilingTask()
        # Should not raise
        task.validate_payload({"data": "col1,col2\n1,2"})

    def test_auto_detect_json(self):
        """Should auto-detect JSON input."""
        task = DatasetProfilingTask()
        # Should not raise
        task.validate_payload({"data": [{"a": 1}]})


# ─────────────────────────────────────────────────────────────────────────
# EXECUTION TESTS
# ─────────────────────────────────────────────────────────────────────────

class TestDatasetProfilingTaskExecution:
    """Test task execution with mocked service."""

    def test_execute_success_csv(self):
        """Should execute CSV profiling successfully."""
        service = FakeProfilingService()
        task = DatasetProfilingTask(service=service)
        payload = {"data": "col1,col2\n1,2"}

        result = task.execute(payload)

        assert result.success is True
        assert result.data["row_count"] == 2
        assert "processing_time_ms" in result.metadata

    def test_execute_success_json(self):
        """Should execute JSON profiling successfully."""
        service = FakeProfilingService()
        task = DatasetProfilingTask(service=service)
        payload = {"data": [{"a": 1}, {"b": 2}]}

        result = task.execute(payload)

        assert result.success is True
        assert isinstance(result.data, dict)

    def test_execute_service_error(self):
        """Should handle service errors gracefully."""
        class FailingService:
            def profile_csv(self, data):
                raise ValueError("Test error")

        task = DatasetProfilingTask(service=FailingService())
        payload = {"data": "col1\n1"}

        result = task.execute(payload)

        assert result.success is False
        assert "Test error" in result.error
```

---

### 2. Integration Tests (Service Layer)

**Scope**: Test `DatasetProfilingService` with real pandas.

**Benefits**:
- Tests actual profiling logic
- Validates type detection
- Tests edge cases
- Slower but comprehensive

**Test file**: `tests/integration/test_dataset_profiling_service.py`

```python
import pytest
import pandas as pd
from ai_engine.application.services.dataset_profiling_service import (
    DatasetProfilingService,
    InvalidInputError,
    ProfilingError,
)


class TestDatasetProfilingServiceCSV:
    """CSV input profiling tests."""

    @pytest.fixture
    def service(self):
        return DatasetProfilingService()

    def test_simple_csv(self, service):
        """Should profile simple CSV."""
        csv = "name,age,salary\nAlice,30,50000\nBob,25,45000\nCharlie,35,60000"
        profile = service.profile_csv(csv)

        assert profile.row_count == 3
        assert profile.column_count == 3
        assert profile.numeric_column_count == 2  # age, salary
        assert profile.categorical_column_count == 1  # name

    def test_csv_with_missing_values(self, service):
        """Should detect and profile missing values."""
        csv = "a,b,c\n1,,3\n4,5,\n7,8,9"
        profile = service.profile_csv(csv)

        # Check null tracking
        col_a = next(c for c in profile.columns if c.name == "a")
        assert col_a.null_count == 0

        col_b = next(c for c in profile.columns if c.name == "b")
        assert col_b.null_count == 1
        assert col_b.null_percentage == 33.33  # (1/3)*100

    def test_numeric_type_detection(self, service):
        """Should detect numeric columns."""
        csv = "int_col,float_col,str_col\n1,1.5,abc\n2,2.5,def"
        profile = service.profile_csv(csv)

        int_col = next(c for c in profile.columns if c.name == "int_col")
        assert int_col.type == "numeric"

        float_col = next(c for c in profile.columns if c.name == "float_col")
        assert float_col.type == "numeric"

        str_col = next(c for c in profile.columns if c.name == "str_col")
        assert str_col.type == "categorical"

    def test_categorical_stats(self, service):
        """Should compute categorical statistics."""
        csv = "color\nred\nred\nblue\ngreen\nred"
        profile = service.profile_csv(csv)

        color_col = profile.columns[0]
        assert color_col.type == "categorical"
        assert color_col.categorical_stats.unique_count == 3
        assert color_col.categorical_stats.top_value == "red"
        assert color_col.categorical_stats.top_count == 3
        assert color_col.categorical_stats.top_percentage == 60.0

    def test_numeric_stats(self, service):
        """Should compute numeric statistics."""
        csv = "score\n10\n20\n30\n40\n50"
        profile = service.profile_csv(csv)

        score_col = profile.columns[0]
        stats = score_col.numeric_stats

        assert stats.min == 10.0
        assert stats.max == 50.0
        assert stats.mean == 30.0
        assert stats.median == 30.0
        assert stats.q25 == 20.0
        assert stats.q75 == 40.0

    def test_outlier_detection(self, service):
        """Should detect outliers using IQR method."""
        csv = "value\n1\n2\n3\n4\n5\n100"
        profile = service.profile_csv(csv)

        col = profile.columns[0]
        assert col.has_outliers is True
        assert col.outlier_count == 1  # 100 is an outlier

    def test_correlations(self, service):
        """Should compute correlations between numeric columns."""
        csv = "x,y\n1,2\n2,4\n3,6\n4,8"
        profile = service.profile_csv(csv)

        assert len(profile.correlations) > 0
        # x and y should be perfectly correlated
        assert profile.correlations.get(("x", "y"), 0) > 0.99

    def test_empty_csv_error(self, service):
        """Should raise error on empty CSV."""
        with pytest.raises(InvalidInputError):
            service.profile_csv("")

    def test_malformed_csv_error(self, service):
        """Should raise error on malformed CSV."""
        with pytest.raises(InvalidInputError):
            service.profile_csv("col1,col2\nvalue_only")


class TestDatasetProfilingServiceJSON:
    """JSON records profiling tests."""

    @pytest.fixture
    def service(self):
        return DatasetProfilingService()

    def test_simple_records(self, service):
        """Should profile simple JSON records."""
        records = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35},
        ]
        profile = service.profile_records(records)

        assert profile.row_count == 3
        assert profile.column_count == 2
        assert profile.numeric_column_count == 1
        assert profile.categorical_column_count == 1

    def test_sparse_schema(self, service):
        """Should handle records with different fields."""
        records = [
            {"a": 1, "b": 2},
            {"a": 3},           # Missing "b"
            {"b": 4, "c": 5},   # Missing "a", has "c"
        ]
        profile = service.profile_records(records)

        assert profile.column_count == 3  # a, b, c

        col_b = next(c for c in profile.columns if c.name == "b")
        assert col_b.null_count == 1  # First record has "b"

    def test_mixed_types(self, service):
        """Should detect mixed-type columns."""
        records = [
            {"value": 1},
            {"value": "string"},
            {"value": 3.5},
        ]
        profile = service.profile_records(records)

        col = profile.columns[0]
        assert col.type == "mixed"

    def test_empty_records_error(self, service):
        """Should raise error on empty records."""
        with pytest.raises(InvalidInputError):
            service.profile_records([])

    def test_non_dict_records_error(self, service):
        """Should raise error on non-dict records."""
        with pytest.raises(InvalidInputError):
            service.profile_records([1, 2, 3])
```

---

### 3. End-to-End Tests

**Scope**: Test complete flow from payload to result.

**Test file**: `tests/e2e/test_dataset_profiling_e2e.py`

```python
import pytest
from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask


class TestDatasetProfilingE2E:
    """End-to-end profiling tests."""

    def test_e2e_csv_flow(self):
        """Complete CSV profiling flow."""
        task = DatasetProfilingTask()
        
        csv = """
        id,name,age,salary,department
        1,Alice,30,50000,Engineering
        2,Bob,25,45000,Sales
        3,Charlie,35,60000,Engineering
        4,Diana,28,48000,Marketing
        5,Eve,32,55000,Sales
        """
        
        payload = {"data": csv.strip()}
        result = task.execute(payload)

        assert result.success is True
        data = result.data

        # Validate dataset-level stats
        assert data["row_count"] == 5
        assert data["column_count"] == 5

        # Validate column detection
        assert data["numeric_column_count"] >= 2  # id, age, salary
        assert data["categorical_column_count"] >= 2  # name, department

        # Validate metadata
        assert result.metadata["processing_time_ms"] > 0
        assert result.metadata["service_version"] == "1.0.0"

    def test_e2e_json_flow(self):
        """Complete JSON records profiling flow."""
        task = DatasetProfilingTask()

        records = [
            {"id": 1, "score": 95.5, "grade": "A"},
            {"id": 2, "score": 87.0, "grade": "B"},
            {"id": 3, "score": 92.5, "grade": "A"},
        ]

        payload = {"data": records}
        result = task.execute(payload)

        assert result.success is True
        assert result.data["row_count"] == 3

    def test_e2e_with_outliers(self):
        """Should detect outliers in E2E flow."""
        task = DatasetProfilingTask()

        csv = "value\n10\n12\n11\n13\n500"  # 500 is outlier

        result = task.execute({"data": csv})

        assert result.success is True
        col = result.data["columns"][0]
        assert col["has_outliers"] is True
        assert col["outlier_count"] > 0
```

---

## Test Fixtures

### Mock Service

```python
from ai_engine.application.services.dataset_profiling_service import (
    DatasetProfile, ColumnProfile, NumericStats
)


class MockDatasetProfilingService:
    """Lightweight mock for testing without pandas."""

    def __init__(self, response: DatasetProfile | None = None):
        self.response = response or self._default_response()
        self.call_count = 0
        self.last_call_args = None

    def profile_csv(self, csv_data: str) -> DatasetProfile:
        self.call_count += 1
        self.last_call_args = ("csv", csv_data)
        return self.response

    def profile_records(self, records: list) -> DatasetProfile:
        self.call_count += 1
        self.last_call_args = ("json", records)
        return self.response

    @staticmethod
    def _default_response() -> DatasetProfile:
        return DatasetProfile(
            row_count=100,
            column_count=3,
            columns=[],
            numeric_column_count=1,
            categorical_column_count=2,
            datetime_column_count=0,
            mixed_column_count=0,
            memory_usage_bytes=10240,
            processing_time_ms=50.0,
        )


@pytest.fixture
def mock_profiling_service():
    return MockDatasetProfilingService()
```

---

## Test Data Sets

### 1. Simple Dataset

```python
SIMPLE_CSV = """name,age,city
Alice,30,NYC
Bob,25,LA
Charlie,35,Chicago"""

SIMPLE_JSON = [
    {"name": "Alice", "age": 30, "city": "NYC"},
    {"name": "Bob", "age": 25, "city": "LA"},
    {"name": "Charlie", "age": 35, "city": "Chicago"},
]
```

### 2. Edge Cases

```python
# All nulls
ALL_NULLS_CSV = "col\n\n\n"

# Mixed types
MIXED_CSV = "value\n1\nabc\n3.5\nNone"

# Large dataset
LARGE_JSON = [{"id": i, "value": i * 2} for i in range(10000)]

# Special characters
SPECIAL_CHARS_CSV = "text\n\"hello,world\"\nline\\nbreak\ntab\there"
```

---

## Coverage Targets

| Module | Target | Critical Paths |
|--------|--------|-----------------|
| `dataset_profiling_service.py` | >90% | Type detection, statistics, correlations |
| `dataset_profiling.py` | >85% | Validation, service invocation, error handling |

---

## Performance Testing

### Latency Benchmarks

```python
import time

def benchmark_profiling():
    service = DatasetProfilingService()

    # Small dataset: 100 rows
    records_small = [{"a": i, "b": i*2} for i in range(100)]
    t0 = time.time()
    service.profile_records(records_small)
    print(f"100 rows: {(time.time()-t0)*1000:.2f} ms")

    # Medium dataset: 10K rows
    records_medium = [{"a": i, "b": i*2} for i in range(10000)]
    t0 = time.time()
    service.profile_records(records_medium)
    print(f"10K rows: {(time.time()-t0)*1000:.2f} ms")

    # Large dataset: 100K rows
    records_large = [{"a": i, "b": i*2} for i in range(100000)]
    t0 = time.time()
    service.profile_records(records_large)
    print(f"100K rows: {(time.time()-t0)*1000:.2f} ms")
```

**Expected results**:
- 100 rows: <50 ms
- 10K rows: 100-300 ms
- 100K rows: 500-2000 ms

---

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/unit/test_dataset_profiling_task.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=ai_engine --cov-report=html
```

### Run Only Unit Tests (fast)

```bash
pytest tests/unit/ -m "not integration"
```

### Run with Markers

```python
# Mark tests
@pytest.mark.unit
def test_validation(): ...

@pytest.mark.integration
def test_with_pandas(): ...

@pytest.mark.slow
def test_large_dataset(): ...
```

```bash
pytest tests/ -m "not slow"  # Skip slow tests
```

---

## Best Practices

### DO ✓

- Mock the service in task tests (no pandas dependency)
- Use fixtures for common test data
- Test both happy path and error cases
- Include boundary condition tests (empty, max size)
- Verify metadata in results
- Test type detection with diverse inputs
- Use parametrized tests for similar cases

### DON'T ✗

- Import pandas in task unit tests
- Test the same scenario in multiple layers
- Use real files in unit tests
- Create massive datasets in memory for tests
- Skip error cases
- Assume column order in assertions
- Test implementation details instead of behavior

---

## Recommended Test Structure

```
tests/
├── conftest.py                          # Shared fixtures
│
├── unit/
│   ├── test_dataset_profiling_task.py  # Task validation & execution
│   └── fixtures/
│       ├── mock_services.py
│       └── test_data.py
│
├── integration/
│   ├── test_dataset_profiling_service.py  # Service with pandas
│   └── fixtures/
│       └── pandas_datasets.py
│
└── e2e/
    └── test_dataset_profiling_e2e.py   # Full flow
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Dataset Profiling Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
          pip install pandas pytest pytest-cov
      
      - name: Run unit tests
        run: pytest tests/unit/ -v
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
      
      - name: Generate coverage
        run: pytest tests/ --cov=ai_engine --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'pandas'"

**Cause**: pandas not installed in test environment.

**Solution**:
```bash
pip install pandas
# OR
pip install -r requirements.txt
```

### Issue: Tests pass locally but fail in CI

**Cause**: Different Python versions or missing dependencies.

**Solution**:
- Test with same Python version locally
- Check `requirements-dev.txt`
- Use docker to match CI environment

### Issue: Flaky outlier detection test

**Cause**: Small sample sizes may not always produce outliers.

**Solution**:
```python
# Use larger dataset
csv = "\n".join(["1", "2", "3"] * 100 + ["1000"])
```

---

## Version & Compatibility

- **Python**: 3.10+
- **pandas**: 1.5+
- **pytest**: 7.0+

---

## Further Reading

- [pytest Documentation](https://pytest.org)
- [Testing Best Practices](https://docs.pytest.org/en/7.1.x/goodpractices.html)
- [pandas Testing Guide](https://pandas.pydata.org/docs/development/contributing.html)
