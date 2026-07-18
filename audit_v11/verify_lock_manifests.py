#!/usr/bin/env python3
"""Verify archived V11 lock hashes from any extracted repository path.

The primary lock retains the absolute paths recorded in the original run.
This verifier maps each archived filename to its release-relative location
without modifying the historical manifest.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit_v11"

PATH_MAP = {
    "TRACE_RISK_STUDY_V11.yaml": ROOT / "config" / "TRACE_RISK_STUDY_V11.yaml",
    "BurstGPT_first100_public.csv": ROOT / "trace_data" / "BurstGPT_first100_public.csv",
    "run_trace_risk_study.py": ROOT / "v11_code" / "run_trace_risk_study.py",
    "TRACE_NONINFERIORITY_FOLLOWUP_V11.yaml": ROOT / "config" / "TRACE_NONINFERIORITY_FOLLOWUP_V11.yaml",
    "run_trace_noninferiority_followup.py": ROOT / "v11_code" / "run_trace_noninferiority_followup.py",
    "trace_risk_runs.csv": ROOT / "v11_results" / "trace_risk_runs.csv",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(manifest: Path) -> None:
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, archived_path = raw.split(maxsplit=1)
        name = Path(archived_path.strip()).name
        target = PATH_MAP.get(name)
        if target is None:
            raise SystemExit(f"No portable mapping for {name}")
        actual = sha256(target)
        status = "OK" if actual == expected else "FAILED"
        print(f"{target.relative_to(ROOT)}: {status}")
        if actual != expected:
            raise SystemExit(
                f"Hash mismatch for {target}: expected {expected}, got {actual}"
            )


if __name__ == "__main__":
    verify(AUDIT / "TRACE_RISK_LOCK_MANIFEST.sha256")
    verify(AUDIT / "TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256")
    print("All archived V11 lock hashes verified.")
