from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import ast
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

required = [
    "README.md",
    "CITATION.cff",
    "LICENSE-CODE",
    "LICENSE-DATA",
    "manuscript/manuscript.tex",
    "manuscript/manuscript.pdf",
    "manuscript/supplementary_material.tex",
    "manuscript/supplementary_material.pdf",
    "data/synthetic/policy_surfaces.csv",
    "data/synthetic/scenario_definitions.csv",
    "results/analytical_validation/optimizer_reanalysis_summary.csv",
    "validation/analytical_validation_report.pdf",
    "protocols/analytical_validation_protocol.json",
    "audit/checksums.sha256",
]
for relative in required:
    if not (ROOT / relative).is_file():
        errors.append(f"Missing required file: {relative}")

version_pattern = re.compile(
    r"(^|/)(?:v\d+[a-z]?(?:[_-]|$)|[^/]*[_-]v\d+[a-z]?(?:[._-]|$))",
    re.IGNORECASE,
)
for path in ROOT.rglob("*"):
    relative = path.relative_to(ROOT).as_posix()
    if version_pattern.search(relative):
        errors.append(f"Development-version identifier in path: {relative}")

for script in (ROOT / "src" / "validation").glob("*.py"):
    try:
        ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    except Exception as exc:
        errors.append(f"Python syntax failure in {script.name}: {exc}")

try:
    surfaces = __import__("pandas").read_csv(ROOT / "data/synthetic/policy_surfaces.csv")
    if len(surfaces) != 36 * 190:
        errors.append(f"Policy surface row count is {len(surfaces)}, expected 6840.")
    if surfaces["scenario_id"].nunique() != 36:
        errors.append("Policy surfaces do not contain 36 scenarios.")
    if surfaces.groupby("scenario_id")["policy_idx"].nunique().min() != 190:
        errors.append("At least one scenario does not contain 190 policies.")
except Exception as exc:
    errors.append(f"Could not validate policy surfaces: {exc}")

checksum_path = ROOT / "audit" / "checksums.sha256"
if checksum_path.is_file():
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        target = ROOT / relative
        if not target.is_file():
            errors.append(f"Checksum target missing: {relative}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            errors.append(f"Checksum mismatch: {relative}")

for pdf in [
    ROOT / "manuscript" / "manuscript.pdf",
    ROOT / "manuscript" / "supplementary_material.pdf",
    ROOT / "validation" / "analytical_validation_report.pdf",
]:
    if pdf.is_file():
        try:
            output = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
            if "Pages:" not in output:
                errors.append(f"Could not read PDF page count: {pdf.name}")
        except Exception as exc:
            errors.append(f"PDF preflight failed for {pdf.name}: {exc}")

status = {
    "status": "PASS" if not errors else "FAIL",
    "errors": errors,
}
print(json.dumps(status, indent=2))
sys.exit(0 if not errors else 1)
