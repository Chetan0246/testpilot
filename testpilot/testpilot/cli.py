"""Command line entry point: `testpilot path/to/module.py`."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import agent
from .llm import NemotronClient


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="testpilot",
                                description="Write and run pytest tests for a Python file with Nemotron on Nebius.")
    p.add_argument("file", help="Python module to test")
    p.add_argument("--rounds", type=int, default=3, help="max run/repair rounds (default 3)")
    p.add_argument("--out", help="where to save the final test file (default tests_generated/test_<name>.py)")
    args = p.parse_args(argv)

    src = Path(args.file)
    if not src.exists() or src.suffix != ".py":
        p.error(f"{src} is not a Python file")

    llm = NemotronClient()
    report = agent.run(src, llm, max_rounds=args.rounds)

    out = Path(args.out) if args.out else Path("tests_generated") / f"test_{src.stem}.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.test_code)

    print("\n" + report.summary())
    u = llm.usage
    print(f"Nemotron calls: {u.calls} ({', '.join(f'{m}: {c}' for m, c in u.by_model.items())}), "
          f"{u.prompt_tokens + u.completion_tokens} tokens, {u.seconds:.1f}s via {getattr(llm, 'provider', 'nebius')}")
    print(f"Saved tests to {out}")
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
