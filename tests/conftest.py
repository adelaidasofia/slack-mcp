"""Collection floor for the CI gate.

`pytest` exits 5 when it collects zero tests. Exit 5 is indistinguishable from
a real pass to any caller that tolerates it, so a suite that collected nothing
reported exactly the same green as a suite that passed. That is not
hypothetical: `tests/integration/test_full_pipeline.py` was once a self-running
`main()` script with no `test_*` functions. pytest collected 0 items, reported
"no tests ran", and the gate stayed green while validating nothing.

This module makes zero collection -- and any collection below the floor -- a
hard failure with exit code 4 (pytest's `UsageError`), a code that no exit-5
escape hatch anywhere in the chain can swallow.

Enforcement is unconditional. It is deliberately NOT auto-disabled for narrowed
invocations, because "which flags narrow collection" is an open set that a
denylist always loses to: `-k`, `-m` and `--deselect` deselect *after* this
hook runs and leave the count intact, but `--lf` and node-id arguments narrow
collection *before* it and would look identical to tests going missing. There
is exactly one way to stand the floor down -- set the floor to 0:

    SLACK_MCP_PYTEST_MIN_TESTS=0 pytest tests/ --lf

`make ci` never sets it, so the canonical gate always runs with the floor up.
"""

from __future__ import annotations

import os

import pytest

#: Floor, not a target. It only fires when tests DISAPPEAR -- deleted, renamed
#: out of `test_*`, or made silently uncollectable. Adding tests never trips it,
#: so this constant needs bumping only if you want the ratchet to climb.
DEFAULT_MIN_TESTS = 23

#: The one and only spelling for "stand the floor down". Any other value that
#: is not a non-negative integer is a hard error, never a silent fallback.
MIN_TESTS_ENV = "SLACK_MCP_PYTEST_MIN_TESTS"


def _floor() -> int:
    """Resolve the collection floor, failing loudly on anything malformed."""
    raw = os.environ.get(MIN_TESTS_ENV)
    if raw is None:
        return DEFAULT_MIN_TESTS
    try:
        value = int(raw)
    except ValueError:
        raise pytest.UsageError(
            f"{MIN_TESTS_ENV}={raw!r} is not an integer. Refusing to fall back "
            f"to the default floor: a guard that silently defaults on a "
            f"malformed value is the fail-open this guard exists to prevent."
        ) from None
    if value < 0:
        raise pytest.UsageError(f"{MIN_TESTS_ENV}={raw!r} must be >= 0.")
    return value


def pytest_collection_modifyitems(session, config, items) -> None:
    floor = _floor()
    collected = len(items)

    # Always announce the floor. A lowered or stood-down floor has to be
    # visible in the run's own output, never inferable only from a green.
    state = "DISABLED" if floor == 0 else f"floor {floor}"
    print(f"\n[ci-gate] collected {collected} test(s), {state}")

    if collected >= floor:
        return

    if collected == 0:
        raise pytest.UsageError(
            "[ci-gate] pytest collected 0 tests. Bare pytest would exit 5 "
            "here, which reads as a pass to any caller that tolerates it. "
            "Failing with exit 4 instead."
        )

    raise pytest.UsageError(
        f"[ci-gate] pytest collected {collected} test(s), below the floor of "
        f"{floor}. Tests went missing: deleted, renamed out of `test_*`, or "
        f"made uncollectable. If you narrowed the run on purpose (--lf, a "
        f"node id), re-run with {MIN_TESTS_ENV}=0. If the drop is real and "
        f"intended, lower DEFAULT_MIN_TESTS in tests/conftest.py in the same "
        f"commit that removes the tests."
    )
