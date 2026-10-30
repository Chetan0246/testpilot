"""The TestPilot agent loop: draft tests -> run -> triage failures -> fix or flag bugs -> repeat."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .llm import extract_code
from .runner import RunResult, run_tests

DRAFT_SYSTEM = """You are TestPilot, an expert Python test engineer.
Write a complete pytest file for the module the user gives you.
Rules:
- Import the module by its file name (e.g. `import {module}` or `from {module} import ...`).
- Test the INTENDED behaviour described by names, docstrings and type hints, not just what the code happens to do.
- Cover normal cases, edge cases (empty, zero, negative, None, large) and expected exceptions.
- Write 8 to 15 small tests. EVERY test must contain at least one `assert` or `pytest.raises`.
- Use only pytest and the standard library. No network, no files outside tmp_path.
- Reply with ONE ```python code block and nothing else."""

TRIAGE_SYSTEM = """You are TestPilot's failure analyst. For each failing test decide:
- "test_bug": the test itself is wrong (bad expectation, wrong import, typo).
- "code_bug": the module under test violates its documented/intended behaviour.
Reply with JSON only: {"verdicts": [{"test": "<test name>", "kind": "test_bug"|"code_bug", "reason": "<one sentence>"}]}"""

FIX_SYSTEM = """You are TestPilot. Rewrite the pytest file so that:
- every test marked test_bug is corrected,
- every test marked code_bug is KEPT but decorated with
  @pytest.mark.xfail(reason="TestPilot found a bug: <reason>", strict=True)
- passing tests are unchanged and are NEVER deleted (return the whole file),
- a collection/import error is fixed first,
- every test keeps at least one `assert` or `pytest.raises` that checks the documented behaviour,
  so an xfail test genuinely fails because of the bug.
Reply with ONE ```python code block containing the full file and nothing else."""


@dataclass
class Round:
    number: int
    model: str
    result: RunResult
    verdicts: list = field(default_factory=list)


@dataclass
class Report:
    source: str
    test_code: str
    rounds: list
    bugs: list
    success: bool

    def summary(self) -> str:
        last = self.rounds[-1].result if self.rounds else None
        lines = [f"TestPilot report for {self.source}",
                 f"Rounds: {len(self.rounds)}  |  Final: "
                 + (f"{last.passed} passed, {last.failed} failed, {last.errors} errors" if last else "n/a")]
        if last and last.coverage is not None:
            lines.append(f"Line coverage: {last.coverage:.0f}%")
        if self.bugs:
            lines.append("Likely bugs in your code:")
            lines += [f"  - {b['test']}: {b['reason']}" for b in self.bugs]
        else:
            lines.append("No bugs flagged in your code.")
        return "\n".join(lines)


_FAILED_NAME = re.compile(r"(?:FAILED|ERROR) \S*::(\w+)")


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"verdicts": []}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {"verdicts": []}


def run(source_path: str | Path, llm, max_rounds: int = 3,
        on_event: Callable[[str], None] = print) -> Report:
    """Generate and iterate on tests for one Python file. `llm` needs a .chat(system, user, strong=bool)."""
    path = Path(source_path)
    module = path.stem
    source = path.read_text()
    bugs: dict[str, str] = {}
    rounds: list[Round] = []

    model_used = llm.fast_model
    on_event(f"Drafting tests for {path.name} with {llm.fast_model} ...")
    test_code = extract_code(llm.chat(DRAFT_SYSTEM.format(module=module),
                                      f"Module `{module}` ({path.name}):\n```python\n{source}\n```"))

    for n in range(1, max_rounds + 1):
        result = run_tests(path, test_code)
        on_event(f"Round {n}: {result.passed} passed, {result.failed} failed, {result.errors} errors"
                 + (f", coverage {result.coverage:.0f}%" if result.coverage is not None else ""))
        rnd = Round(n, model_used, result)
        rounds.append(rnd)
        if result.ok or n == max_rounds:
            break

        # Escalate to the stronger Nemotron model on the last repair attempt.
        strong = n == max_rounds - 1
        failing = sorted(set(_FAILED_NAME.findall(result.output)))
        ctx = (f"Module `{module}`:\n```python\n{source}\n```\n\nTest file:\n```python\n{test_code}\n```\n\n"
               f"pytest output:\n```\n{result.output[-4000:]}\n```\nFailing tests: {failing or 'see output'}")
        verdicts = _parse_json(llm.chat(TRIAGE_SYSTEM, ctx, strong=strong)).get("verdicts", [])
        rnd.verdicts = verdicts
        for v in verdicts:
            if v.get("kind") == "code_bug":
                bugs[v.get("test", "?")] = v.get("reason", "")
                on_event(f"  Bug suspected in your code -> {v.get('test')}: {v.get('reason')}")
            else:
                on_event(f"  Fixing test -> {v.get('test')}")
        model_used = llm.strong_model if strong else llm.fast_model
        on_event(f"Repairing tests with {model_used} ...")
        test_code = extract_code(llm.chat(
            FIX_SYSTEM, ctx + f"\n\nVerdicts:\n```json\n{json.dumps(verdicts, indent=1)}\n```", strong=strong))

    final = rounds[-1].result
    return Report(path.name, test_code, rounds,
                  [{"test": k, "reason": v} for k, v in bugs.items()], final.ok)
