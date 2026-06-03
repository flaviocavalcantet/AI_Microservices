# Dataset Profiling: Output Schema Reference

## Overview

The Dataset Profiling service generates comprehensive statistical profiles of datasets (CSV or JSON). This document defines the complete output structure, data types, and field meanings.

## Response Structure

```json
{
  "success": true,
  "data": {
    // Dataset-level statistics
    "row_count": <int>,
    "column_count": <int>,
    "numeric_column_count": <int>,
    "categorical_column_count": <int>,
    "datetime_column_count": <int>,
    "mixed_column_count": <int>,
    "memory_usage_bytes": <int>,
    "processing_time_ms": <float>,
    
    // Per-column details
    "columns": [
      {
        "name": <str>,
        "type": <str>,  // "numeric" | "categorical" | "datetime" | "mixed" | "unknown"
        "total_count": <int>,
        "null_count": <int>,
        "null_percentage": <float>,  // 0-100
        "unique_count": <int>,
        "duplicate_count": <int>,
        "sample_values": [<str>, ...],  // up to 5 samples
        "has_outliers": <bool>,
        "outlier_count": <int>,
        
        // Type-specific statistics (optional)
        "numeric_stats": { ... },      // if type is "numeric"
        "categorical_stats": { ... },  // if type is "categorical"
      },
      ...
    ],
    
    // Pearson correlations between numeric columns
    "correlations": {
      "col1_col2": <float>,  // -1.0 to 1.0
      ...
    }
  },
  "metadata": {
    "processing_time_ms": <float>,
    "service_version": "1.0.0"
  }
}
```

## Field Definitions

### Dataset-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `row_count` | int | Total number of rows in the dataset |
| `column_count` | int | Total number of columns |
| `numeric_column_count` | int | Number of columns identified as numeric |
| `categorical_column_count` | int | Number of columns identified as categorical |
| `datetime_column_count` | int | Number of columns identified as datetime |
| `mixed_column_count` | int | Number of columns with mixed types |
| `memory_usage_bytes` | int | Approximate memory footprint of the dataset (bytes) |
| `processing_time_ms` | float | Total time to generate profile (milliseconds) |

### Column Profile Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Column name/identifier |
| `type` | str | Detected data type: `numeric`, `categorical`, `datetime`, `mixed`, or `unknown` |
| `total_count` | int | Total entries in column (including nulls) |
| `null_count` | int | Number of null/missing values |
| `null_percentage` | float | Percentage of null values (0-100) |
| `unique_count` | int | Number of distinct non-null values |
| `duplicate_count` | int | Number of duplicate values (total - unique) |
| `sample_values` | list[str] | Up to 5 sample values (non-null) for preview |
| `has_outliers` | bool | Whether outliers were detected (numeric columns only) |
| `outlier_count` | int | Number of detected outliers using IQR method |

### Numeric Statistics (`numeric_stats`)

Present when `type == "numeric"`.

```json
{
  "min": <float>,           // Minimum value
  "max": <float>,           // Maximum value
  "mean": <float>,          // Arithmetic mean
  "median": <float>,        // Middle value (50th percentile)
  "std_dev": <float>,       // Standard deviation
  "q25": <float>,           // 25th percentile (Q1)
  "q75": <float>,           // 75th percentile (Q3)
  "count": <int>            // Count of numeric values used
}
```

**Outlier Detection**: Uses IQR (Interquartile Range) method:
- IQR = Q75 - Q25
- Lower bound = Q25 - 1.5 × IQR
- Upper bound = Q75 + 1.5 × IQR
- Values outside bounds are flagged as outliers

### Categorical Statistics (`categorical_stats`)

Present when `type == "categorical"`.

```json
{
  "unique_count": <int>,      // Total distinct values
  "top_value": <str>,         // Most common value
  "top_count": <int>,         // Frequency of top value
  "top_percentage": <float>,  // Percentage of dataset that is top value
  "count": <int>              // Count of categorical values used
}
```

### Correlations

Pearson correlation coefficients between all pairs of numeric columns:

```json
{
  "column1_column2": 0.85,    // Strong positive correlation
  "column1_column3": -0.42,   // Weak negative correlation
  "column2_column3": 0.12     // Weak positive correlation
}
```

**Interpretation**:
- `1.0` = perfect positive correlation
- `-1.0` = perfect negative correlation
- `0.0` = no linear relationship

## Data Type Detection Algorithm

The service uses a multi-step algorithm to classify columns:

### 1. Datetime Detection
- Checks if pandas recognizes the column as `datetime64` dtype
- Returns `"datetime"` if true

### 2. Numeric Detection
- Checks if pandas recognizes the column as numeric dtype
- Falls back to sampling: converts sample of values to float
- If ≥80% of samples convert successfully → `"numeric"`

### 3. Mixed Type Detection
- Examines first 50 non-null values
- If multiple distinct Python types found → `"mixed"`

### 4. Default
- All other cases → `"categorical"` (including strings, booleans, etc.)

## Example Response

```json
{
  "success": true,
  "data": {
    "row_count": 1000,
    "column_count": 4,
    "numeric_column_count": 2,
    "categorical_column_count": 2,
    "datetime_column_count": 0,
    "mixed_column_count": 0,
    "memory_usage_bytes": 65536,
    "processing_time_ms": 145.3,
    "columns": [
      {
        "name": "age",
        "type": "numeric",
        "total_count": 1000,
        "null_count": 5,
        "null_percentage": 0.5,
        "unique_count": 87,
        "duplicate_count": 913,
        "sample_values": ["25", "42", "31", "58", "19"],
        "has_outliers": true,
        "outlier_count": 3,
        "numeric_stats": {
          "min": 18.0,
          "max": 95.0,
          "mean": 42.5,
          "median": 41.0,
          "std_dev": 15.2,
          "q25": 32.0,
          "q75": 52.0,
          "count": 995
        }
      },
      {
        "name": "category",
        "type": "categorical",
        "total_count": 1000,
        "null_count": 0,
        "null_percentage": 0.0,
        "unique_count": 5,
        "duplicate_count": 995,
        "sample_values": ["A", "B", "A", "C", "B"],
        "has_outliers": false,
        "outlier_count": 0,
        "categorical_stats": {
          "unique_count": 5,
          "top_value": "A",
          "top_count": 320,
          "top_percentage": 32.0,
          "count": 1000
        }
      }
    ],
    "correlations": {
      "age_income": 0.78
    }
  },
  "metadata": {
    "processing_time_ms": 145.3,
    "service_version": "1.0.0"
  }
}
```

## Error Response

When profiling fails:

```json
{
  "success": false,
  "error": "CSV data cannot be empty",
  "data": {},
  "metadata": {}
}
```

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Min dataset size | 1 row | Requires at least one record |
| Max records | 1,000,000 | Safety limit to prevent OOM |
| Max CSV size | 100 MB | Prevents memory exhaustion |
| Typical latency | 50-500 ms | Depends on dataset size and complexity |
| Memory overhead | ~2x dataset size | Pandas DataFrame + statistics |

## Missing Values

- **Definition**: Null, None, NaN, or empty strings (in JSON context)
- **Tracking**: `null_count` and `null_percentage` fields
- **Calculation**: `null_percentage = (null_count / total_count) * 100`
- **Numeric stats**: Computed only on non-null values
- **Categorical stats**: Computed only on non-null values

## Column Type Priorities

When a column has mixed characteristics:

1. **Datetime** (highest priority)
   - If recognized as pandas datetime64

2. **Numeric**
   - If pandas dtype is numeric
   - OR if ≥80% of sampled values convert to float

3. **Mixed**
   - If multiple Python types found in first 50 values

4. **Categorical** (default)
   - Everything else, including strings

## Notes

- All floating-point values in output are rounded to 6 decimal places for JSON compatibility
- Percentages are rounded to 4 decimal places
- Correlations are rounded to 6 decimal places
- Sample values are converted to strings for JSON serialization
- Processing time includes pandas initialization (if not cached)
- Outlier counts are included even for non-numeric columns (always 0)
