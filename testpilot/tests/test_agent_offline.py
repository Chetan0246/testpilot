"""Offline tests for TestPilot's loop, using a scripted fake LLM (no API key needed)."""
import json
from pathlib import Path

from testpilot import agent
from testpilot.llm import extract_code
from testpilot.runner import run_tests

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "inventory.py"

GOOD = '''```python
from inventory import Inventory, apply_discount
import pytest

def test_add_and_count():
    inv = Inventory(); inv.add("apple", 3)
    assert inv.count("apple") == 3

def test_discount():
    assert apply_discount(100, 15) == 85.0
```'''

WRONG_TEST = GOOD.replace("== 85.0", "== 80.0")

BUGGY_EXPECT = '''```python
from inventory import Inventory
import pytest

def test_items_sorted():
    inv = Inventory(); inv.add("pear", 1); inv.add("apple", 1)
    assert inv.items() == ["apple", "pear"]
```'''

XFAILED = '''```python
from inventory import Inventory
import pytest

@pytest.mark.xfail(reason="TestPilot found a bug: items() is not sorted", strict=True)
def test_items_sorted():
    inv = Inventory(); inv.add("pear", 1); inv.add("apple", 1)
    assert inv.items() == ["apple", "pear"]

def test_count_unknown():
    assert Inventory().count("x") == 0
```'''


class FakeLLM:
    fast_model, strong_model = "fake-nano", "fake-super"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, system, user, strong=False, temperature=0.2):
        self.calls.append(strong)
        return self.replies.pop(0)


def test_extract_code_strips_think_and_fences():
    assert extract_code("<think>hmm</think>```python\nx = 1\n```") == "x = 1\n"


def test_runner_counts_pass_and_fail():
    ok = run_tests(EXAMPLE, extract_code(GOOD))
    assert ok.ok and ok.passed == 2 and ok.coverage is not None
    bad = run_tests(EXAMPLE, extract_code(WRONG_TEST))
    assert not bad.ok and bad.failed == 1


def test_loop_passes_first_try():
    llm = FakeLLM([GOOD])
    rep = agent.run(EXAMPLE, llm, on_event=lambda m: None)
    assert rep.success and len(rep.rounds) == 1 and rep.bugs == []


def test_loop_repairs_a_wrong_test():
    verdict = json.dumps({"verdicts": [{"test": "test_discount", "kind": "test_bug", "reason": "math"}]})
    llm = FakeLLM([WRONG_TEST, verdict, GOOD])
    rep = agent.run(EXAMPLE, llm, on_event=lambda m: None)
    assert rep.success and len(rep.rounds) == 2


def test_loop_flags_real_bug_and_escalates():
    verdict = json.dumps({"verdicts": [{"test": "test_items_sorted", "kind": "code_bug",
                                        "reason": "items() is not sorted"}]})
    llm = FakeLLM([BUGGY_EXPECT, verdict, XFAILED])
    rep = agent.run(EXAMPLE, llm, max_rounds=2, on_event=lambda m: None)
    assert rep.success
    assert rep.bugs == [{"test": "test_items_sorted", "reason": "items() is not sorted"}]
    assert llm.calls[1:] == [True, True]  # last repair used the strong model
