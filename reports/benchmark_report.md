# CDC Pipeline Performance Benchmark Report

## System Environment
- **Operating System:** Windows (win32)
- **Python Version:** 3.10.0
- **CPU Cores:** 8
- **Total RAM:** 7.3 GB

## Empirical Benchmark Results

| Dataset Size (Records) | Execution Time (s) | Throughput (Records/Sec) | Peak Memory (MB) | Valid Records | Rejected | Duplicates |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.379 | 2,636.13 | 99.11 | 935 | 72 | 1 |
| 10,000 | 3.872 | 2,582.74 | 125.07 | 9,402 | 605 | 1 |
| 100,000 | 42.032 | 2,379.14 | 289.41 | 94,180 | 5,827 | 1 |

## Optimization Techniques Employed
1. **Chunked Streaming**: Streaming generator with configurable batch size prevents memory saturation.
2. **SQLite WAL Mode & Memory Cache**: `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` maximize disk write performance.
3. **In-Memory Cache Layer**: Pre-loaded lookup indices eliminate per-row SELECT queries, scaling O(1) per lookup.
4. **Bulk Transaction Persistence**: SQLAlchemy bulk operations (`bulk_insert_mappings`) minimize ORM object overhead.