# Dataset Profiling: Validation Rules & Constraints

## Overview

This document defines all validation rules, constraints, and error handling for the Dataset Profiling service.

## Input Validation

### 1. Payload Structure

**Rule**: Payload must be a dictionary containing a `data` key.

```python
# ✓ Valid
{"data": "col1,col2\n1,2\n3,4"}
{"data": [{"col1": 1, "col2": 2}]}

# ✗ Invalid
{"datasets": [...]}  # Missing 'data' key
"col1,col2\n1,2"     # Not a dictionary
```

**Error**: `ValueError: Payload must contain a 'data' key with CSV string or JSON records.`

---

### 2. Input Type Detection & Override

**Rule**: Input type is auto-detected or specified via `input_type` field.

```python
# Auto-detection
{"data": "csv,data"}           # Detected as "csv"
{"data": [{"a": 1}]}           # Detected as "json"

# Explicit specification
{"data": "csv,data", "input_type": "csv"}
{"data": [{"a": 1}], "input_type": "json"}

# Manual override (if auto-detection fails)
{"data": "unusual,format", "input_type": "csv"}
```

**Valid input_type values**: `"csv"`, `"json"`, `"auto"`

**Error**: `ValueError: Cannot auto-detect input type. data must be str (CSV) or list (JSON records), got: <type>`

---

### 3. CSV Input Validation

#### 3.1 Format

**Rule**: CSV must be a valid string parseable by pandas.

```python
# ✓ Valid formats
"col1,col2,col3\n1,2,3\n4,5,6"
"a;b;c\n1;2;3"  # Custom delimiter detected by pandas
"Name,Age,Email\nJohn,30,john@example.com"

# ✗ Invalid formats
""                           # Empty string
"col1,col2\n1,2\n1,"       # Malformed (trailing comma)
None                         # Not a string
```

**Error**: `ValueError: CSV data cannot be empty` or `ValueError: Failed to parse CSV: <pandas error>`

#### 3.2 Size Limits

**Rule**: CSV data must not exceed 100 MB.

```python
# ✓ Valid
csv_data = "col1,col2\n" + "\n".join([f"{i},{i+1}" for i in range(10000)])

# ✗ Invalid
csv_data = "x" * (101 * 1024 * 1024)  # 101 MB
```

**Constraint**: `_MAX_CSV_SIZE_MB = 100`

**Error**: `ValueError: CSV exceeds maximum size of 100 MB`

#### 3.3 Content Requirements

**Rule**: CSV must contain valid data (at least 1 row after header).

```python
# ✓ Valid
"a,b\n1,2"           # 1 data row
"x\n1\n2\n3"         # 3 data rows

# ✗ Invalid
"a,b"                # Header only, no data
"a,b,c\n"            # Header with empty trailing row
```

---

### 4. JSON Records Input Validation

#### 4.1 Structure

**Rule**: JSON data must be a list of dictionaries.

```python
# ✓ Valid
[{"a": 1, "b": 2}]
[{"a": 1}, {"a": 2, "b": 3}]  # Flexible schema
[
  {"id": 1, "name": "Alice", "age": 30},
  {"id": 2, "name": "Bob", "age": 25}
]

# ✗ Invalid
{"a": 1}                        # Not a list
[1, 2, 3]                       # List of non-dicts
[{"a": 1}, None, {"b": 2}]     # Contains None
[{"a": 1}, "string"]           # Mixed types
```

**Error**: 
- `ValueError: Records list cannot be empty`
- `ValueError: JSON records must be a list, got: <type>`
- `ValueError: All JSON records must be dictionaries`

#### 4.2 Record Count

**Rule**: JSON must contain between 1 and 1,000,000 records.

```python
# ✓ Valid
[{"a": 1}]                           # 1 record
[{"a": i} for i in range(100)]       # 100 records

# ✗ Invalid
[]                                    # 0 records
[{"a": i} for i in range(1_000_001)] # 1,000,001 records
```

**Constraints**:
- `_MIN_RECORDS = 1`
- `_MAX_RECORDS = 1_000_000`

**Error**: `ValueError: Too many records (<count>). Maximum: 1,000,000`

#### 4.3 Schema Flexibility

**Rule**: Records can have different fields (sparse schema).

```python
# ✓ Valid - flexible schema
[
  {"a": 1, "b": 2, "c": 3},
  {"a": 4, "b": 5},           # Missing "c"
  {"a": 6, "d": 7}            # Different fields
]
```

The service:
1. Discovers all unique keys across records
2. Treats missing keys as null values
3. Profiles each column independently

---

## Data Type Handling

### 5. Null/Missing Value Handling

**Rule**: Null, None, and empty values are tracked separately.

```python
# NULL DETECTION (JSON records):
{"value": None}           # Python None → null
{"value": ""}             # Empty string → treated as valid string
{"value": float("nan")}   # NaN → null in CSV context

# NULL DETECTION (CSV):
"a,b\n1,\n3,4"            # Empty field → null
"a,b\n1,2\n3,\n"          # Trailing comma → null
```

**Null Counting**:
- `null_count`: Sum of all None/NaN values
- `null_percentage`: (null_count / total_count) × 100
- Statistics computed on non-null values only

---

### 6. Numeric Type Detection

**Rule**: Column is "numeric" if convertible to float.

```python
# Detection algorithm:
1. Check if pandas recognizes as numeric (int, float, etc.)
   → "numeric"

2. If not, sample first 100 values:
   - Try converting each to float()
   - If ≥80% succeed → "numeric"
   - Otherwise → continue

3. If <80% numeric → check for mixed types
```

**Examples**:

```python
# ✓ Detected as numeric
[1, 2, 3]                           # Integers
[1.5, 2.5, 3.5]                     # Floats
["1", "2", "3"]                     # String numbers (>80% convertible)
[1, 2.5, None, 3]                   # Mixed with nulls

# ✗ NOT detected as numeric
["1", "abc", "3"]                   # <80% convertible
["apple", "banana", "cherry"]       # All non-numeric
[True, False, True]                 # Booleans (detected as categorical)
["2024-01-01", "2024-01-02"]       # Datetime strings
```

**Conversion Strategy**:
- `int` → kept as is
- `float` → kept as is
- `"123"` → converted to float
- `"123.45"` → converted to float
- `"abc"` → conversion fails

---

### 7. Categorical Type Detection

**Rule**: Column is "categorical" by default if not numeric/datetime/mixed.

```python
# ✓ Examples of categorical columns
["A", "B", "A", "C"]                # Strings
[True, False, True]                 # Booleans
["red", "green", "blue"]            # Strings
```

**Advantages**:
- More permissive than numeric
- Works for all string data
- Includes enums and codes

---

### 8. Datetime Type Detection

**Rule**: Column recognized as datetime by pandas.

```python
import pandas as pd

# ✓ Detected as datetime
pd.Series(["2024-01-01", "2024-01-02"])  # ISO format
pd.Series(pd.to_datetime(["2024-01-01"]))  # Actual datetime64

# ✗ NOT detected
["01/01/2024", "02/01/2024"]  # Ambiguous format (treated as categorical)
["Jan 1, 2024", "Jan 2, 2024"]  # Non-standard format
```

**Note**: The service relies on pandas' datetime detection. Custom formats may be classified as categorical.

---

### 9. Mixed Type Detection

**Rule**: Column with multiple Python types → "mixed".

```python
# ✓ Detected as mixed
[1, "abc", 2.5, None]               # int, str, float
[True, "string", 42]                # bool, str, int
[{"a": 1}, [1, 2, 3], "text"]      # dict, list, str
```

**Detection**:
- Examines first 50 non-null values
- Counts distinct Python `type()` names
- If >1 type found → "mixed"

---

## Statistical Constraints

### 10. Numeric Statistics

**Rule**: Statistics only computed on non-null numeric values.

```python
Series: [1, 2, None, 4, 5]
Used for stats: [1, 2, 4, 5]

Results:
- count: 4 (not including None)
- mean: (1+2+4+5)/4 = 3.0
- min: 1, max: 5
```

**Methods**:
- `min`: Smallest value
- `max`: Largest value
- `mean`: Arithmetic mean
- `median`: 50th percentile
- `std_dev`: Standard deviation (NaN if n=1)
- `q25`: 25th percentile (Q1)
- `q75`: 75th percentile (Q3)

---

### 11. Outlier Detection

**Rule**: Uses Interquartile Range (IQR) method.

```python
IQR = Q75 - Q25
Lower bound = Q25 - 1.5 × IQR
Upper bound = Q75 + 1.5 × IQR

Values outside [lower, upper] → outliers
```

**Example**:
```python
Values: [1, 2, 3, 4, 5, 100]
Q25 = 2.25, Q75 = 4.75, IQR = 2.5
Lower = 2.25 - 3.75 = -1.5
Upper = 4.75 + 3.75 = 8.5
Outliers: [100] (> 8.5)
outlier_count = 1
```

---

### 12. Categorical Statistics

**Rule**: Top value and distribution computed from non-null values.

```python
Values: ["A", "B", "A", "C", "A", None]
Non-null: ["A", "B", "A", "C", "A"]

top_value: "A" (most frequent)
top_count: 3
top_percentage: (3/6) × 100 = 50%
unique_count: 3 (A, B, C)
count: 5 (excluding None)
```

---

### 13. Correlation Computation

**Rule**: Pearson correlation only for numeric column pairs.

```python
# Columns selected for correlation
Numeric columns: [age, income, score]
Pairs: (age, income), (age, score), (income, score)

# Correlation results
"age_income": 0.78
"age_score": 0.12
"income_score": 0.65
```

**Properties**:
- Only numeric columns included
- Coerces non-numeric to NaN
- Skips correlations with <2 valid values
- Returns -1.0 to 1.0 range
- NaN correlations omitted from results

---

## Error Handling

### 14. Exception Hierarchy

```
DatasetProfilingError (base)
├── DatasetProfilingImportError
│   └── "pandas is required..."
├── InvalidInputError
│   ├── "Payload must contain 'data'..."
│   ├── "CSV data cannot be empty..."
│   ├── "CSV exceeds maximum size..."
│   ├── "Records list cannot be empty..."
│   └── "All JSON records must be dictionaries..."
└── ProfilingError
    └── "Dataset profiling failed: ..."
```

### 15. Error Response Format

All errors return AIJobResult with `success=False`:

```python
{
  "success": False,
  "error": "CSV data cannot be empty",
  "data": {},
  "metadata": {}
}
```

**Error messages**:
- Descriptive and actionable
- Include constraint details where relevant
- Not exposing internal stack traces to client

---

## Performance & Safety Boundaries

| Constraint | Value | Reason |
|-----------|-------|--------|
| Max CSV size | 100 MB | Memory efficiency |
| Max records | 1,000,000 | Memory efficiency |
| Min records | 1 | Statistical validity |
| Min text length | 1 char | Flexibility |
| Numeric threshold | 80% | Type detection robustness |
| Sample size | 5 values | JSON payload size |
| Correlation pairs | O(n²) where n = numeric cols | N/A (typical: <50 numeric cols) |
| Datetime formats | Built-in pandas detection | Standard formats only |

---

## Validation Flowchart

```
Input Payload
    ↓
Has 'data' key? → No → Error
    ↓ Yes
Detect/Get input_type
    ↓
Type = "csv"?
    ├─ Yes → Is string? → No → Error
    │            ↓ Yes
    │         Is empty? → Yes → Error
    │            ↓ No
    │         < 100 MB? → No → Error
    │            ↓ Yes
    │         Parse CSV → Success/Error
    │
    └─ Type = "json"?
         ├─ Yes → Is list? → No → Error
         │           ↓ Yes
         │        All dicts? → No → Error
         │           ↓ Yes
         │        Not empty? → No → Error
         │           ↓ Yes
         │        ≤ 1M records? → No → Error
         │           ↓ Yes
         │        Convert to DataFrame → Success/Error
         │
         └─ Type = "auto"?
              └─ Apply auto-detection logic above
```

---

## Best Practices

### DO ✓

- Always include the `data` key in payload
- Use `input_type: "csv"` or `"json"` if type is known (faster than auto-detection)
- Validate CSV before sending (check for BOM, encoding)
- Keep datasets under 10,000 records for optimal performance
- Use numeric types (int, float) in JSON when possible (not strings)
- Include correlation analysis for feature engineering workflows

### DON'T ✗

- Send empty datasets (minimum 1 record required)
- Mix CSV and JSON in same request
- Send extremely large files (>100 MB may timeout)
- Assume column order is preserved (it is, but don't rely on it)
- Use special CSV delimiters without testing (let pandas auto-detect)
- Send binary or non-text data as CSV

---

## Version History

- **v1.0.0** (current): Initial release with CSV, JSON, and pandas support
