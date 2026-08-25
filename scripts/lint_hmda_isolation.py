# This project was developed with assistance from AI tools.
"""Cross-platform HMDA data-isolation boundary check."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages" / "api" / "src"


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def scan(patterns: list[str], excluded_fragments: list[str]) -> list[str]:
    compiled = [re.compile(pattern) for pattern in patterns]
    violations: list[str] = []
    for path in SOURCE.rglob("*.py"):
        rel = relative(path)
        if any(fragment in rel for fragment in excluded_fragments):
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(pattern.search(line) for pattern in compiled):
                violations.append(f"{rel}:{line_no}:{line.strip()}")
    return violations


def main() -> int:
    checks = [
        (
            "HMDA schema references found outside services/compliance/",
            [r"schema\s*=\s*['\"]hmda['\"]", r"['\"]hmda\."],
            ["services/compliance/"],
        ),
        (
            "Compliance pool imports found outside allowed paths",
            [r"\bget_compliance_db\b", r"\bComplianceSessionLocal\b", r"\bcompliance_engine\b"],
            [
                "services/compliance/",
                "routes/hmda.py",
                "routes/admin.py",
                "src/main.py",
                "src/seed.py",
            ],
        ),
        (
            "HMDA model imported outside services/compliance/",
            [r"\bHmdaDemographic\b", r"\bHmdaLoanData\b"],
            ["services/compliance/", "schemas/hmda.py", "routes/hmda.py"],
        ),
    ]

    print("Checking HMDA isolation boundaries...")
    failed = False
    for title, patterns, exclusions in checks:
        violations = scan(patterns, exclusions)
        if not violations:
            continue
        failed = True
        print(f"\nVIOLATION: {title}:")
        print("\n".join(violations))
    if failed:
        print("\nHMDA data access must go through services/compliance/ only.")
        return 1
    print("HMDA isolation check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
