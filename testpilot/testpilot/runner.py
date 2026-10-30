"""Runs generated pytest files in an isolated temp directory and summarises the result."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    passed: int
    failed: int
    errors: int
    coverage: float | None
    output: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.failed == 0 and self.errors == 0 and self.passed > 0


_COUNT = re.compile(r"(\d+) (passed|failed|error|errors)")


def run_tests(source_path: Path, test_code: str, timeout: int = 60) -> RunResult:
    """Copy the module under test plus the test file into a sandbox dir and run pytest."""
    source_path = Path(source_path).resolve()
    work = Path(tempfile.mkdtemp(prefix="testpilot_"))
    try:
        shutil.copy(source_path, work / source_path.name)
        test_file = work / f"test_{source_path.stem}.py"
        test_file.write_text(test_code)
        cov_json = work / "cov.json"
        cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
               f"--cov={source_path.stem}", f"--cov-report=json:{cov_json}", test_file.name]
        try:
            proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            return RunResult(0, 0, 1, None, f"Timed out after {timeout}s\n{e.stdout or ''}", True)
        out = (proc.stdout + "\n" + proc.stderr).strip()
        counts = {"passed": 0, "failed": 0, "error": 0}
        for n, kind in _COUNT.findall(out.splitlines()[-1] if out else ""):
            counts["error" if kind.startswith("error") else kind] += int(n)
        if not any(counts.values()) and proc.returncode != 0:
            counts["error"] = 1  # collection/import error
        coverage = None
        if cov_json.exists():
            try:
                coverage = json.loads(cov_json.read_text())["totals"]["percent_covered"]
            except (KeyError, ValueError):
                pass
        return RunResult(counts["passed"], counts["failed"], counts["error"], coverage, out[-6000:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
