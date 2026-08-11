"""Negative controls for the CI gate itself.

A guard earns trust only by failing on the thing it catches. These tests drive
the two shipped layers -- `tests/conftest.py` and the `ci` target in the
`Makefile` -- through the failure modes they exist to stop, and assert each one
comes back non-zero with a code nothing downstream tolerates.

They also assert the passing paths, because a guard that fails unconditionally
would satisfy every negative control while breaking the suite for real work.

Exit codes that matter here:
  0 = pass
  4 = pytest UsageError -- what the collection floor raises
  5 = no tests collected -- the code this whole gate exists to stop swallowing

`make` reports 2 for any failed recipe and never propagates the recipe's own
code, so the Makefile-level controls assert the property callers depend on
(non-zero, and never 5) rather than an exact code make cannot deliver.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_CONFTEST = Path(__file__).resolve().parent / "conftest.py"
MIN_TESTS_ENV = "SLACK_MCP_PYTEST_MIN_TESTS"

NO_TESTS_COLLECTED = 5
USAGE_ERROR = 4


def _run_pytest_in(tmp_path: Path, files: dict[str, str], floor: str | None):
    """Run pytest against a scratch `tests/` tree carrying the REAL conftest.

    The shipped conftest is copied in byte-for-byte rather than reimplemented,
    so these controls exercise the artifact that actually gates CI.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(REAL_CONFTEST, tests_dir / "conftest.py")
    for name, body in files.items():
        (tests_dir / name).write_text(body, encoding="utf-8")

    env = dict(os.environ)
    env.pop(MIN_TESTS_ENV, None)
    if floor is not None:
        env[MIN_TESTS_ENV] = floor

    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )


def _run_make_ci(tmp_path: Path, stub_exit_code: int):
    """Drive the SHIPPED `make ci` recipe with a stub standing in for pytest.

    Overriding PYTEST lets the recipe's exit-code handling be tested in
    isolation, without a real collection run deciding the outcome.
    """
    if shutil.which("make") is None:
        pytest.skip("make not on PATH")
    if os.name != "posix":
        pytest.skip("stub interpreter is a POSIX shell script")

    stub = tmp_path / "fake-pytest"
    stub.write_text(f"#!/bin/sh\nexit {stub_exit_code}\n", encoding="utf-8")
    stub.chmod(0o755)

    return subprocess.run(
        ["make", "ci", f"PYTEST={stub}"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


# --------------------------------------------------------------------------
# Layer 1: the collection floor in tests/conftest.py
# --------------------------------------------------------------------------

def test_zero_collection_fails_with_a_code_nothing_swallows(tmp_path: Path) -> None:
    """The core bug: an empty tests dir must not report green."""
    result = _run_pytest_in(tmp_path, files={}, floor=None)
    assert result.returncode != 0, (
        f"zero collection reported success.\n{result.stdout}\n{result.stderr}"
    )
    assert result.returncode != NO_TESTS_COLLECTED, (
        "zero collection exited 5, the exact code the Makefile and test.yml "
        f"tolerate -- the gate is still swallowable.\n{result.stdout}"
    )
    assert result.returncode == USAGE_ERROR, (
        f"expected exit {USAGE_ERROR}, got {result.returncode}\n{result.stdout}"
    )
    assert "collected 0 tests" in result.stdout + result.stderr


def test_collection_broken_by_import_error_fails(tmp_path: Path) -> None:
    """A tests dir that cannot be imported must not report green either."""
    result = _run_pytest_in(
        tmp_path,
        files={"test_broken.py": "import definitely_not_a_real_module_xyz\n"},
        floor=None,
    )
    assert result.returncode != 0, (
        f"broken collection reported success.\n{result.stdout}\n{result.stderr}"
    )
    assert result.returncode != NO_TESTS_COLLECTED, (
        f"broken collection exited 5 and is swallowable.\n{result.stdout}"
    )


def test_partial_collection_below_floor_fails(tmp_path: Path) -> None:
    """Tests silently going missing must fail, not just total disappearance."""
    result = _run_pytest_in(
        tmp_path,
        files={"test_one.py": "def test_only_survivor(): pass\n"},
        floor="5",
    )
    assert result.returncode == USAGE_ERROR, (
        f"1 collected against a floor of 5 should fail with {USAGE_ERROR}, "
        f"got {result.returncode}\n{result.stdout}"
    )
    assert "below the floor of 5" in result.stdout + result.stderr


def test_collection_at_or_above_floor_passes(tmp_path: Path) -> None:
    """The guard must have a passing path, or every control above is vacuous."""
    result = _run_pytest_in(
        tmp_path,
        files={"test_two.py": "def test_a(): pass\ndef test_b(): pass\n"},
        floor="2",
    )
    assert result.returncode == 0, (
        f"2 collected against a floor of 2 should pass, got "
        f"{result.returncode}\n{result.stdout}\n{result.stderr}"
    )
    assert "[ci-gate] collected 2 test(s), floor 2" in result.stdout


def test_malformed_floor_is_a_hard_error_not_a_silent_default(tmp_path: Path) -> None:
    """A guard that silently defaults on garbage input is a fail-open."""
    result = _run_pytest_in(
        tmp_path,
        files={"test_one.py": "def test_only(): pass\n"},
        floor="not-an-integer",
    )
    assert result.returncode == USAGE_ERROR, (
        f"malformed floor should hard-error, got {result.returncode}\n{result.stdout}"
    )
    assert "is not an integer" in result.stdout + result.stderr


def test_floor_zero_is_the_documented_stand_down(tmp_path: Path) -> None:
    """Exactly one spelling stands the floor down, and it must actually work."""
    result = _run_pytest_in(
        tmp_path,
        files={"test_one.py": "def test_only(): pass\n"},
        floor="0",
    )
    assert result.returncode == 0, (
        f"floor 0 should permit a narrowed run, got {result.returncode}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "DISABLED" in result.stdout, (
        f"a stood-down floor must say so in the run's own output.\n{result.stdout}"
    )


# --------------------------------------------------------------------------
# Layer 2: exit-5 normalization in the Makefile, which survives conftest loss
# --------------------------------------------------------------------------

def test_makefile_never_hands_exit_five_onward(tmp_path: Path) -> None:
    """`make ci` must not emit 5, the one code test.yml still tolerates."""
    result = _run_make_ci(tmp_path, stub_exit_code=NO_TESTS_COLLECTED)
    assert result.returncode != 0, (
        f"make ci reported success for a zero-collection run.\n{result.stdout}"
    )
    assert result.returncode != NO_TESTS_COLLECTED, (
        f"make ci handed exit {NO_TESTS_COLLECTED} onward to test.yml, whose "
        f"`[ \"$code\" = \"5\" ]` tolerance would turn it green.\n{result.stdout}"
    )
    assert "collected 0 tests" in result.stdout


def test_makefile_preserves_real_outcomes(tmp_path: Path) -> None:
    """Normalization must not mask a real pass or soften a real failure.

    `make` collapses every failed recipe to exit 2 and never propagates the
    recipe's own code, so the contract worth asserting is the one callers
    actually depend on: 0 stays 0, and a failure stays a non-zero that is not
    the swallowable 5.
    """
    assert _run_make_ci(tmp_path, stub_exit_code=0).returncode == 0, (
        "make ci turned a passing run into a failure"
    )
    failure = _run_make_ci(tmp_path, stub_exit_code=2)
    assert failure.returncode != 0, "make ci turned a real failure green"
    assert failure.returncode != NO_TESTS_COLLECTED, (
        "make ci mapped a real failure onto the swallowable exit 5"
    )
