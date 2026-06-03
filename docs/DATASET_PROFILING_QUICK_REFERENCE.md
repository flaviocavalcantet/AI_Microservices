# Dataset Profiling: Quick Reference Guide

> One-page reference for common usage patterns and API

---

## Installation

```bash
pip install pandas>=1.5.0
```

---

## Basic Usage

### Profile CSV Data

```python
from ai_engine.application.services.dataset_profiling_service import (
    get_default_service
)

service = get_default_service()

csv_data = """id,name,age,salary
1,Alice,30,50000
2,Bob,25,45000
3,Charlie,35,60000"""

profile = service.profile_csv(csv_data)

print(f"Rows: {profile.row_count}")
print(f"Columns: {profile.column_count}")
print(f"Numeric columns: {profile.numeric_column_count}")
print(f"Categorical columns: {profile.categorical_column_count}")
```

### Profile JSON Records

```python
records = [
    {"id": 1, "score": 95.5, "status": "active"},
    {"id": 2, "score": 87.0, "status": "active"},
    {"id": 3, "score": None, "status": "inactive"}
]

profile = service.profile_records(records)

# Convert to dict for JSON serialization
profile_dict = profile.to_dict()
```

---

## Via AIJobOrchestrator

```python
from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
from ai_engine.domain.models import AIJob, AIJobType

# Create task
task = DatasetProfilingTask()

# Create job payload
payload = {
    "data": "col1,col2,col3\n1,2,3\n4,5,6",
    "input_type": "csv"  # optional: auto-detect by default
}

# Execute
result = task.execute(payload)

# Check result
if result.success:
    print(f"Profile: {result.data}")
    print(f"Time: {result.metadata['processing_time_ms']}ms")
else:
    print(f"Error: {result.error}")
```

---

## Testing (No Pandas Required)

```python
import pytest
from ai_engine.application.tasks.dataset_profiling import DatasetProfilingTask
from ai_engine.application.services.dataset_profiling_service import (
    DatasetProfile, ColumnProfile
)

class MockService:
    def profile_csv(self, data):
        return DatasetProfile(
            row_count=10,
            column_count=2,
            columns=[],
            numeric_column_count=1,
            categorical_column_count=1,
            datetime_column_count=0,
            mixed_column_count=0,
            memory_usage_bytes=1024,
            processing_time_ms=50.0,
        )
    
    def profile_records(self, records):
        return self.profile_csv("")

def test_profiling():
    task = DatasetProfilingTask(service=MockService())
    result = task.execute({"data": "a,b\n1,2"})
    assert result.success
```

---

## API Reference

### DatasetProfilingService

```python
class DatasetProfilingService:
    
    def profile_csv(self, csv_data: str) -> DatasetProfile:
        """
        Profile CSV string.
        
        Args:
            csv_data: CSV content as string
            
        Raises:
            DatasetProfilingImportError: pandas not installed
            InvalidInputError: CSV is empty or malformed
            ProfilingError: Profiling computation failed
        """
    
    def profile_records(self, records: list) -> DatasetProfile:
        """
        Profile JSON records (list of dicts).
        
        Args:
            records: List of record dictionaries
            
        Raises:
            DatasetProfilingImportError: pandas not installed
            InvalidInputError: records invalid or empty
            ProfilingError: Profiling computation failed
        """


def get_default_service() -> DatasetProfilingService:
    """Get or create singleton service (thread-safe)."""
```

### DatasetProfile

```python
@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    numeric_column_count: int
    categorical_column_count: int
    datetime_column_count: int
    mixed_column_count: int
    memory_usage_bytes: int
    processing_time_ms: float
    correlations: dict[tuple[str, str], float]
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
```

### ColumnProfile

```python
@dataclass
class ColumnProfile:
    name: str
    type: Literal["numeric", "categorical", "datetime", "mixed", "unknown"]
    total_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    duplicate_count: int
    sample_values: list[Any]
    numeric_stats: Optional[NumericStats]
    categorical_stats: Optional[CategoricalStats]
    has_outliers: bool
    outlier_count: int
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
```

### NumericStats

```python
@dataclass
class NumericStats:
    min: float
    max: float
    mean: float
    median: float
    std_dev: float
    q25: float
    q75: float
    count: int
```

### CategoricalStats

```python
@dataclass
class CategoricalStats:
    unique_count: int
    top_value: Any
    top_count: int
    top_percentage: float
    count: int
```

---

## Common Patterns

### Extract Specific Column Profile

```python
profile = service.profile_csv("a,b,c\n1,x,3.5\n2,y,4.5")

# Find column by name
age_profile = next(c for c in profile.columns if c.name == 'age')

print(f"Type: {age_profile.type}")
print(f"Nulls: {age_profile.null_count}")
print(f"Stats: {age_profile.numeric_stats}")
```

### Check for Outliers

```python
outlier_columns = [
    c.name for c in profile.columns 
    if c.has_outliers
]
print(f"Columns with outliers: {outlier_columns}")
```

### Get Correlations

```python
# Correlations only for numeric column pairs
for (col1, col2), correlation in profile.correlations.items():
    if correlation > 0.8:
        print(f"Strong correlation: {col1} <-> {col2} = {correlation}")
```

### Handle Missing Values

```python
null_summary = [
    {
        "column": c.name,
        "null_count": c.null_count,
        "null_percentage": c.null_percentage
    }
    for c in profile.columns
    if c.null_count > 0
]

for col_info in null_summary:
    print(f"{col_info['column']}: {col_info['null_percentage']:.2f}% missing")
```

### Export to JSON

```python
import json

profile = service.profile_csv(csv_data)
profile_json = json.dumps(profile.to_dict(), indent=2)

# Save to file
with open('profile.json', 'w') as f:
    f.write(profile_json)
```

---

## Error Handling

```python
from ai_engine.application.services.dataset_profiling_service import (
    DatasetProfilingError,
    InvalidInputError,
    ProfilingError,
    DatasetProfilingImportError,
)

service = get_default_service()

try:
    profile = service.profile_csv(csv_data)
except DatasetProfilingImportError as e:
    print(f"Missing pandas: {e}")
except InvalidInputError as e:
    print(f"Invalid input: {e}")
except ProfilingError as e:
    print(f"Profiling failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Input Validation

### Valid CSV Formats

```python
# Standard CSV
"a,b,c\n1,2,3\n4,5,6"

# With headers
"name,age,score\nAlice,30,95\nBob,25,87"

# Auto-delimiter detection
"a;b;c\n1;2;3"  # Semicolon delimiter

# Large datasets
service.profile_csv(csv_large)  # Up to 100 MB
```

### Valid JSON Formats

```python
# List of dicts
[{"a": 1, "b": 2}, {"a": 3, "b": 4}]

# Flexible schema (different keys per record)
[{"a": 1, "b": 2}, {"a": 3, "c": 4}]

# Up to 1M records
[{"x": i} for i in range(1_000_000)]

# Null values
[{"value": 1}, {"value": None}, {"value": 3}]
```

---

## Performance Tips

| Scenario | Recommendation |
|----------|---|
| Small datasets (<1K rows) | Use JSON (easier) |
| Large datasets (>100K rows) | Use CSV (faster parsing) |
| Real-time profiling | Keep under 10K rows |
| Batch processing | Parallel invocations recommended |
| Memory constrained | Profile in chunks |

---

## Payload Structure

### Request Format

```python
# Minimal (auto-detect type)
{"data": "csv,or,list"}

# Explicit CSV
{"data": "col1,col2\n1,2", "input_type": "csv"}

# Explicit JSON
{"data": [{"a": 1}], "input_type": "json"}
```

### Response Format

```python
{
    "success": True,
    "data": {
        "row_count": 100,
        "column_count": 5,
        "numeric_column_count": 2,
        "categorical_column_count": 3,
        "columns": [...],
        "correlations": {...}
    },
    "metadata": {
        "processing_time_ms": 145.3,
        "service_version": "1.0.0"
    }
}
```

---

## Type Detection Rules

| Data | Detected As |
|------|---|
| `[1, 2, 3]` | numeric |
| `[1.5, 2.5]` | numeric |
| `["1", "2", "3"]` | numeric (if ≥80% convert) |
| `["a", "b", "c"]` | categorical |
| `[2024-01-01, 2024-01-02]` | datetime (if pandas recognizes) |
| `[1, "a", 3.5]` | mixed |

---

## Troubleshooting

### "pandas is required"
```bash
pip install pandas>=1.5.0
```

### Empty dataset error
```python
# Minimum 1 record required
[{"a": 1}]  # ✓ Valid
[]          # ✗ Invalid
```

### CSV parsing fails
```python
# Check CSV format
import pandas as pd
pd.read_csv("your_csv.txt")  # Test locally first
```

### Memory issues with large datasets
```python
# Split into chunks
chunk_size = 100_000
for i in range(0, len(records), chunk_size):
    chunk = records[i:i+chunk_size]
    profile = service.profile_records(chunk)
```

---

## Limits & Constraints

| Constraint | Value |
|-----------|-------|
| Min records | 1 |
| Max records | 1,000,000 |
| Max CSV size | 100 MB |
| Max processing time | ~15 seconds (1M records) |
| Typical latency (10K rows) | 100-300 ms |
| Type detection threshold | 80% numeric |
| Outlier detection method | IQR (1.5×) |

---

## Related Documentation

- 📄 [Implementation Summary](DATASET_PROFILING_IMPLEMENTATION_SUMMARY.md)
- 📄 [Output Schema](DATASET_PROFILING_OUTPUT_SCHEMA.md)
- 📄 [Validation Rules](DATASET_PROFILING_VALIDATION_RULES.md)
- 📄 [Testing Guide](DATASET_PROFILING_TESTING_GUIDE.md)

---

## Version Info

- **Service Version**: 1.0.0
- **Python**: 3.10+
- **pandas**: 1.5+
- **Last Updated**: June 2026
