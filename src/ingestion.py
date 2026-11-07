"""
Data Ingestion Module for CDC Data Pipeline.
Reads CSV and JSON source files in streaming batches and computes cryptographic file hashes.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Generator, List, Dict, Any, Tuple
import pandas as pd


def compute_file_hash(filepath: Path) -> str:
    """Computes SHA-256 hash of a file for idempotency checks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class IngestionError(Exception):
    """Raised when ingestion fails due to invalid file format or accessibility."""
    pass


def read_records(
    filepath: Path,
    batch_size: int = 5000,
) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Generator that yields batches of raw dictionary records from CSV or JSON files.
    Supports standard CSV, JSON arrays, and line-delimited JSON (JSONL).
    """
    if not filepath.exists():
        raise IngestionError(f"File not found: {filepath}")

    if filepath.stat().st_size == 0:
        # Empty file yields nothing
        return

    suffix = filepath.suffix.lower()

    if suffix == ".csv":
        try:
            # First check if file is empty or whitespace
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                first_line = f.readline().strip()
                if not first_line:
                    return

            # Read CSV in chunks using pandas
            for chunk_df in pd.read_csv(
                filepath,
                chunksize=batch_size,
                dtype=str,  # Read all as string initially to prevent auto-truncation/coercion
                keep_default_na=False,
            ):
                records = chunk_df.to_dict(orient="records")
                if records:
                    yield records
        except Exception as e:
            raise IngestionError(f"Error parsing CSV file {filepath}: {str(e)}") from e

    elif suffix in (".json", ".jsonl"):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().strip()
                if not content:
                    return

            # Detect if it is JSON array or JSONL
            if content.startswith("["):
                raw_data = json.loads(content)
                if not isinstance(raw_data, list):
                    raise IngestionError("Top-level JSON structure must be a list of objects.")
                for i in range(0, len(raw_data), batch_size):
                    batch = raw_data[i : i + batch_size]
                    # Ensure records are dictionaries
                    batch_dicts = [r if isinstance(r, dict) else {"_raw": r} for r in batch]
                    yield batch_dicts
            else:
                # Line-delimited JSON
                batch = []
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        record = json.loads(line_str)
                        if isinstance(record, dict):
                            batch.append(record)
                        else:
                            batch.append({"_raw": record})

                        if len(batch) >= batch_size:
                            yield batch
                            batch = []
                if batch:
                    yield batch
        except Exception as e:
            raise IngestionError(f"Error parsing JSON file {filepath}: {str(e)}") from e
    else:
        raise IngestionError(f"Unsupported file format: {suffix}. Only .csv, .json, .jsonl are supported.")


def count_file_records(filepath: Path) -> int:
    """Fast pre-scan to estimate total record count for progress bars."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        return 0

    suffix = filepath.suffix.lower()
    count = 0
    if suffix == ".csv":
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                header = f.readline()
                if not header.strip():
                    return 0
                for line in f:
                    if line.strip():
                        count += 1
            return count
        except Exception:
            return 0
    elif suffix in (".json", ".jsonl"):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                first_char = f.read(1)
                f.seek(0)
                if first_char == "[":
                    data = json.load(f)
                    return len(data) if isinstance(data, list) else 0
                else:
                    for line in f:
                        if line.strip():
                            count += 1
                    return count
        except Exception:
            return 0
    return 0
