"""Run project quality checks before committing or submitting."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


SCANNABLE_SUFFIXES = {
    ".css",
    ".gitignore",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}

EXCLUDED_PATH_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".streamlit",
    ".venv",
    "__pycache__",
    "evaluation_results",
}

CJK_PATTERN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
SECRET_PATTERNS = [
    ("NVIDIA API key pattern", re.compile(r"\bnvapi-[A-Za-z0-9_\-]{8,}\b")),
    ("OpenAI API key pattern", re.compile(r"\bsk-[A-Za-z0-9_\-]{4,}\b")),
    ("Generic API key assignment", re.compile(r"\b[A-Z0-9_]*API_KEY\s*=\s*[\"'][^\"']{8,}[\"']")),
]


@dataclass(frozen=True)
class CommandCheck:
    """A shell-free command check to run from the project root."""

    name: str
    command: List[str]


@dataclass(frozen=True)
class ScanIssue:
    """A text scan issue found in a repository file."""

    path: Path
    line_number: int
    message: str


def build_command_checks(
    python_executable: str,
    template_path: Optional[str] = None,
    samples_path: Optional[str] = None,
    summary_json: Optional[str] = None,
    summary_md: Optional[str] = None,
) -> List[CommandCheck]:
    """Build the core quality commands."""
    checks = [
        CommandCheck(
            "unit tests",
            [
                python_executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ],
        ),
        CommandCheck(
            "compile check",
            [
                python_executable,
                "-m",
                "compileall",
                "-q",
                "app.py",
                "config.py",
                "evaluate_checker.py",
                "modules",
                "tests",
            ],
        ),
    ]

    if template_path and samples_path:
        command = [
            python_executable,
            "evaluate_checker.py",
            "--template",
            template_path,
            "--samples",
            samples_path,
            "--auto-fix-evaluation",
        ]
        if summary_json:
            command.extend(["--summary-json", summary_json])
        if summary_md:
            command.extend(["--summary-md", summary_md])
        checks.append(CommandCheck("evaluation smoke test", command))

    return checks


def is_scannable_text_file(path: Path) -> bool:
    """Return True when a repository file should be scanned as text."""
    parts = set(path.parts)
    if parts.intersection(EXCLUDED_PATH_PARTS):
        return False
    if path.suffix.lower() in SCANNABLE_SUFFIXES:
        return True
    return path.name in SCANNABLE_SUFFIXES


def find_non_english_markers(text: str) -> List[Tuple[int, str]]:
    """Find CJK characters in text files that should remain English-only."""
    issues = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if CJK_PATTERN.search(line):
            issues.append((line_number, "CJK character detected"))
    return issues


def find_secret_markers(text: str) -> List[Tuple[int, str]]:
    """Find common API-key patterns without returning the secret value."""
    issues = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        matched_specific = False
        for message, pattern in SECRET_PATTERNS[:2]:
            if pattern.search(line):
                issues.append((line_number, message))
                matched_specific = True
        if matched_specific:
            continue
        for message, pattern in SECRET_PATTERNS[2:]:
            if pattern.search(line):
                issues.append((line_number, message))
    return issues


def iter_git_files(project_root: Path) -> List[Path]:
    """Return tracked and untracked repository paths, excluding ignored files."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to list git files")
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def scan_repository_text(project_root: Path, paths: Iterable[Path]) -> List[ScanIssue]:
    """Scan text files for non-English text and secret markers."""
    issues: List[ScanIssue] = []
    for relative_path in paths:
        if not is_scannable_text_file(relative_path):
            continue
        absolute_path = project_root / relative_path
        try:
            text = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = absolute_path.read_text(encoding="utf-8", errors="ignore")

        for line_number, message in find_non_english_markers(text):
            issues.append(ScanIssue(relative_path, line_number, message))
        for line_number, message in find_secret_markers(text):
            issues.append(ScanIssue(relative_path, line_number, message))
    return issues


def run_command_check(project_root: Path, check: CommandCheck) -> int:
    """Run one command check and stream its output."""
    print(f"\n== {check.name} ==")
    print(" ".join(check.command))
    completed = subprocess.run(check.command, cwd=project_root, check=False)
    if completed.returncode == 0:
        print(f"OK: {check.name}")
    else:
        print(f"FAILED: {check.name} exited with {completed.returncode}")
    return completed.returncode


def run_quality_gate(args: argparse.Namespace) -> int:
    """Run scans and command checks."""
    project_root = Path(args.project_root).resolve()
    exit_code = 0

    print(f"Project root: {project_root}")
    scan_paths = iter_git_files(project_root)
    scan_issues = scan_repository_text(project_root, scan_paths)
    print("\n== text and secret scan ==")
    if scan_issues:
        for issue in scan_issues:
            print(f"FAILED: {issue.path}:{issue.line_number}: {issue.message}")
        exit_code = 1
    else:
        print("OK: no CJK text or API-key patterns found in scannable files")

    with tempfile.TemporaryDirectory() as temp_dir:
        summary_json = str(Path(temp_dir) / "evaluation_summary.json")
        summary_md = str(Path(temp_dir) / "evaluation_summary.md")
        checks = build_command_checks(
            sys.executable,
            template_path=args.template,
            samples_path=args.samples,
            summary_json=summary_json,
            summary_md=summary_md,
        )
        if not args.template or not args.samples:
            print("\nSkipping evaluation smoke test. Provide --template and --samples to enable it.")

        for check in checks:
            if run_command_check(project_root, check) != 0:
                exit_code = 1

    if exit_code == 0:
        print("\nAll quality checks passed.")
    else:
        print("\nQuality checks failed.")
    return exit_code


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the quality gate CLI parser."""
    parser = argparse.ArgumentParser(description="Run FYP project quality checks.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--template", default=None)
    parser.add_argument("--samples", default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run_quality_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
