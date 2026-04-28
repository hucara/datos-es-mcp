"""
Shared pytest fixtures and integration test helpers.

integration_report fixture
--------------------------
Session-scoped callable fixture used by integration tests to record each
tool call result. Writes ``integration_report.json`` (next to this file)
during fixture teardown, after all tests have run.

Usage inside a test:

    async def test_something(report):
        result = await some_tool_fn(...)
        report("tool_name", {"param": "value"}, result, claim="the claim text")
        assert ...
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ── Integration test helpers (used by test_integration_*.py) ──────────────────


class _MockMCP:
    def __init__(self):
        self.fn = None

    def tool(self):
        def decorator(fn):
            self.fn = fn
            return fn

        return decorator


def make_tool(register_fn):
    mcp = _MockMCP()
    register_fn(mcp)
    return mcp.fn


def skip_network(exc):
    pytest.skip(f"Network unavailable: {type(exc).__name__}: {exc}")


def extract_floats(text: str) -> list[float]:
    """Extract numeric values from text, stripping date prefixes to avoid false positives."""
    cleaned = re.sub(r"\b(19|20)\d{2}-\d{2}(?:-\d{2})?", " ", text)
    cleaned = re.sub(r"\b(19|20)\d{2}\b", " ", cleaned)
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", cleaned)]


def text_block(
    text: str, start_label: str, end_label: str | None = None, window: int = 600
) -> str:
    """Extract text between start_label and end_label (or window chars)."""
    s = text.find(start_label)
    if s == -1:
        return ""
    end = text.find(end_label, s + 1) if end_label else s + window
    if end == -1:
        end = s + window
    return text[s:end]


def values_after(text: str, label: str, window: int = 300) -> list[float]:
    """Return floats found within window chars after label."""
    return extract_floats(text_block(text, label, window=window))


def assert_tool_ok(result: str) -> None:
    assert not result.startswith("Error"), f"Tool returned error: {result[:200]}"
    assert not result.startswith("No data returned"), f"No data: {result[:200]}"


_REPORT_PATH = Path(__file__).parent / "integration_report.json"


class _Reporter:
    """Accumulates tool-call records during a test session."""

    def __init__(self):
        self._records: list[dict[str, Any]] = []
        self._current_test: str = ""

    def set_test(self, name: str) -> None:
        self._current_test = name

    def __call__(
        self,
        tool: str,
        params: dict,
        output: str,
        claim: str = "",
    ) -> None:
        self._records.append(
            {
                "test": self._current_test,
                "claim": claim,
                "tool": tool,
                "params": params,
                "output": output,
                "output_length": len(output),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Live output when running with -s / --capture=no
        sep = "─" * 60
        print(f"\n{sep}")
        print(f"TEST  : {self._current_test}")
        if claim:
            print(f"CLAIM : {claim}")
        print(f"TOOL  : {tool}({_fmt_params(params)})")
        print(f"OUTPUT ({len(output)} chars):")
        print(output)
        print(sep)

    @property
    def records(self) -> list[dict]:
        return list(self._records)


def _fmt_params(params: dict) -> str:
    return ", ".join(
        f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}" for k, v in params.items()
    )


@pytest.fixture(scope="session")
def report():
    reporter = _Reporter()
    yield reporter

    # Teardown: write JSON report after all tests have finished
    if not reporter.records:
        return

    report_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_calls": len(reporter.records),
        "calls": reporter.records,
    }
    _REPORT_PATH.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"\n📄 Integration report → {_REPORT_PATH} ({len(reporter.records)} calls recorded)"
    )


@pytest.fixture(autouse=True)
def _set_reporter_test_name(request, report):
    """Keep the reporter's current test name in sync."""
    report.set_test(request.node.nodeid)
    yield
