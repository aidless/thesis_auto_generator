#!/usr/bin/env python3
"""Recompute the README result table from the unit suite and the git tree.

This command does not call DeepSeek, Semantic Scholar, Crossref, or any other
network API. It fails if README.md disagrees with the values just measured.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

KEYS = (
    "unittest_passed",
    "unittest_failed",
    "unittest_errors",
    "unittest_skipped",
    "test_files",
    "test_functions",
    "tracked_output_files",
    "tracked_e2e_logs",
    "tracked_review_files",
    "ethics_clauses",
    "app_version",
)

# Strings that used to be presented as results and are not recomputed here.
FORBIDDEN_IN_README = (
    "真实文献",
    "¥",
    "17,056",
    "17,486",
    "18,809",
    "major_revision",
    "0.06",
    "0.05",
    "189/189",
)


class ClaimError(Exception):
    """The README does not match a value this process just measured."""


def read_app_version(root: Path) -> str:
    tree = ast.parse((root / "config.py").read_text(encoding="utf-8"))
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign):
            target = node.targets[0] if node.targets else None
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if (
            isinstance(target, ast.Name)
            and target.id == "APP_VERSION"
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            return value.value
    raise ClaimError('config.py is missing a string assignment APP_VERSION = "..."')


def count_test_functions(root: Path) -> tuple[int, int]:
    files = sorted((root / "tests").glob("test_*.py"))
    total = 0
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        total += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
    return len(files), total


def git_tracked(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ClaimError("git ls-files failed; the result counts tracked files only")
    return [item for item in proc.stdout.decode().split("\0") if item]


def run_unittests(root: Path) -> unittest.TestResult:
    loader = unittest.TestLoader()
    suite = loader.discover(
        str(root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(root),
    )
    return unittest.TextTestRunner(verbosity=1).run(suite)


def compute_live(root: Path) -> dict[str, str]:
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    version = read_app_version(root)
    files, functions = count_test_functions(root)
    result = run_unittests(root)
    failed = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    if result.expectedFailures or result.unexpectedSuccesses:
        raise ClaimError("expected failures are not part of this result")
    passed = result.testsRun - failed - errors - skipped
    tracked = git_tracked(root)
    output_files = [path for path in tracked if path.startswith("data/output/")]
    logs = [path for path in tracked if path.endswith(".log")]
    reviews = [
        path for path in tracked if path.startswith("data/") and "review" in path.lower()
    ]
    from utils.watermark import (  # noqa: WPS433 — after the suite, on purpose
        DISCLAIMER_BODY,
        ETHICS_NO_FABRICATION,
        ETHICS_NO_PLAGIARISM,
        ETHICS_NO_SUBMIT,
    )

    clauses = (ETHICS_NO_SUBMIT, ETHICS_NO_FABRICATION, ETHICS_NO_PLAGIARISM)
    ethics = sum(clause in DISCLAIMER_BODY for clause in clauses)
    return {
        "unittest_passed": str(passed),
        "unittest_failed": str(failed),
        "unittest_errors": str(errors),
        "unittest_skipped": str(skipped),
        "test_files": str(files),
        "test_functions": str(functions),
        "tracked_output_files": str(len(output_files)),
        "tracked_e2e_logs": str(len(logs)),
        "tracked_review_files": str(len(reviews)),
        "ethics_clauses": str(ethics),
        "app_version": version,
    }


def parse_check_table(text: str) -> dict[str, str]:
    match = re.search(r"<!-- CHECK:BEGIN -->\s*(.*?)<!-- CHECK:END -->", text, re.S)
    if not match:
        raise ClaimError("README.md is missing the CHECK block")
    rows: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            raise ClaimError(f"CHECK row must have 2 cells: {line}")
        key, value = cells
        if key == "key" or re.fullmatch(r":?-{3,}:?", key):
            continue
        if key in rows:
            raise ClaimError(f"duplicate CHECK key {key}")
        rows[key] = value
    return rows


def compare_claims(live: dict[str, str], declared: dict[str, str]) -> None:
    missing = [key for key in KEYS if key not in declared]
    extra = [key for key in declared if key not in KEYS]
    if missing or extra:
        raise ClaimError(f"CHECK keys missing={missing} extra={extra}")
    drifted = [key for key in KEYS if live[key] != declared[key]]
    if drifted:
        detail = ", ".join(
            f"{key}: live {live[key]} != readme {declared[key]}" for key in drifted
        )
        raise ClaimError(detail)


def problem_lines(text: str) -> list[str]:
    body: list[str] = []
    started = False
    for line in text.splitlines()[1:]:
        if not line.strip():
            if started:
                break
            continue
        if line.startswith(("#", "<!--", "[")):
            break
        started = True
        body.append(line)
    return body


def title_version(text: str) -> str:
    first = text.splitlines()[0].strip()
    match = re.fullmatch(r"# 论文自动生成系统 v(\d+\.\d+)", first)
    if not match:
        raise ClaimError(
            f"title must be '# 论文自动生成系统 vX.Y', got {first!r}"
        )
    return match.group(1)


def stray_numbers(text: str, version: str) -> list[tuple[str, str]]:
    match = re.search(r"<!-- CHECK:BEGIN -->.*?<!-- CHECK:END -->", text, re.S)
    if not match:
        raise ClaimError("README.md is missing the CHECK block")
    outside = text[: match.start()] + text[match.end() :]
    outside = outside.replace(f"v{version}", "vVERSION", 1)
    found: list[tuple[str, str]] = []
    for line in outside.splitlines():
        for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", line):
            found.append((number, line.strip()))
    return found


def prove_comparator_can_fail() -> None:
    """In-memory proof that a drifted value and a stray digit are rejected."""
    zeros = {key: ("2.2" if key == "app_version" else "0") for key in KEYS}
    compare_claims(zeros, dict(zeros))
    drifted = dict(zeros)
    drifted["unittest_passed"] = "1"
    try:
        compare_claims(zeros, drifted)
    except ClaimError:
        pass
    else:
        raise ClaimError("compare_claims did not fail when a value drifted")
    dirty = (
        "# 论文自动生成系统 v9.9\n\n"
        "问题\n\n"
        "<!-- CHECK:BEGIN -->\n| key | value |\n| --- | --- |\n"
        "| app_version | 9.9 |\n<!-- CHECK:END -->\n\n共 4 处\n"
    )
    if not any(number == "4" for number, _line in stray_numbers(dirty, "9.9")):
        raise ClaimError("stray number scan missed a number outside the table")
    clean = dirty.replace("共 4 处", "没有数字")
    if stray_numbers(clean, "9.9"):
        raise ClaimError("stray number scan flagged a clean README")


def surface_uses_shared_version(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for name in (
        "ETHICS_NO_SUBMIT",
        "ETHICS_NO_FABRICATION",
        "ETHICS_NO_PLAGIARISM",
        "APP_VERSION",
    ):
        if name not in text:
            raise ClaimError(f"{path} does not reference {name}")
    if re.search(r"v\d+\.\d+", text):
        raise ClaimError(f"{path} hardcodes a version literal")


def main() -> int:
    prove_comparator_can_fail()
    root = ROOT
    live = compute_live(root)
    for key in KEYS:
        print(f"  {key} = {live[key]}")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for phrase in FORBIDDEN_IN_README:
        if phrase in readme:
            raise ClaimError(f"README still contains withdrawn claim {phrase!r}")
    compare_claims(live, parse_check_table(readme))
    version = live["app_version"]
    if title_version(readme) != version:
        raise ClaimError("title version != APP_VERSION")
    lines = problem_lines(readme)
    if not 1 <= len(lines) <= 3:
        raise ClaimError(f"problem statement must be 1 to 3 lines, got {len(lines)}")
    from utils.watermark import (  # noqa: WPS433
        ETHICS_NO_FABRICATION,
        ETHICS_NO_PLAGIARISM,
        ETHICS_NO_SUBMIT,
    )

    problem = "\n".join(lines)
    for phrase in (ETHICS_NO_SUBMIT, ETHICS_NO_FABRICATION, ETHICS_NO_PLAGIARISM):
        if phrase not in problem:
            raise ClaimError(f"problem statement is missing {phrase}")
    before = readme.split("<!-- CHECK:BEGIN -->", 1)[0]
    if "make check" not in before or "限度" not in before:
        raise ClaimError("opening must state make check and its limits before the table")
    stray = stray_numbers(readme, version)
    if stray:
        rendered = "; ".join(f"{number} in {line}" for number, line in stray)
        raise ClaimError(f"README numbers outside the CHECK table: {rendered}")
    surface_uses_shared_version(root / "app.py")
    surface_uses_shared_version(root / "ui" / "tabs.py")
    report = (root / "docs" / "system-report.md").read_text(encoding="utf-8")
    prereg = (root / "PREREG.md").read_text(encoding="utf-8")
    modes = (root / "FAILURE_MODES.md").read_text(encoding="utf-8")
    if f"v{version}" not in "\n".join(report.splitlines()[:20]):
        raise ClaimError("docs/system-report.md header is missing APP_VERSION")
    if "未复算声明" not in report:
        raise ClaimError("docs/system-report.md is missing 未复算声明")
    if f"v{version}" not in "\n".join(prereg.splitlines()[:20]):
        raise ClaimError("PREREG.md header is missing APP_VERSION")
    if "未证实" not in prereg:
        raise ClaimError("PREREG.md is missing 未证实")
    for needle in (
        "17,056",
        "run_e2e_v3.py",
        "20261112_094756_source.docx",
        ETHICS_NO_FABRICATION,
    ):
        if needle not in modes:
            raise ClaimError(f"FAILURE_MODES.md is missing {needle}")
    print("make check: OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ClaimError as exc:
        print(f"make check: FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
