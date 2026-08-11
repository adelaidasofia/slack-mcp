# Canonical CI gate. `make ci` is the ONE command both CI (test.yml, auto-
# managed by gh-harden-repos.sh) and the local pre-push gate (ci-test) run,
# so they cannot drift.
#
# Exit 5 (pytest collected nothing) is NOT tolerated. This target used to end
# in `|| [ $$? -eq 5 ]`, which made a zero-collection run report exactly the
# same green as a fully passing one -- and that is precisely what a suite of
# self-running scripts with no `test_*` functions produced here.
#
# Two independent layers close it, because test.yml tolerates exit 5 on its
# own side and is regenerated from a template this repo does not own:
#
#   1. tests/conftest.py fails zero-or-below-floor collection with exit 4 --
#      a code no exit-5 escape hatch anywhere in the chain can swallow.
#   2. This target maps a bare exit 5 to a hard failure, so the gate stays
#      closed even if that conftest is deleted. Note that `make` reports 2 for
#      ANY failed recipe and does not propagate the recipe's own code, so what
#      a caller actually observes from `make ci` is 0 for a pass and 2 for a
#      failure -- never 5. That is the whole point: test.yml's `[ "$$code" =
#      "5" ]` tolerance is unreachable through this target.
#
# PYTEST is overridable so the gate's own negative controls can drive this
# recipe with a stub interpreter (see tests/test_ci_gate.py).
PYTEST ?= pytest

.PHONY: ci
ci:
	@$(PYTEST) tests/ -v --strict-markers; \
	code=$$?; \
	if [ $$code -eq 5 ]; then \
		echo "make ci: FAILURE -- pytest collected 0 tests (exit 5)."; \
		echo "make ci: a gate that runs nothing is not a gate that passed."; \
		exit 1; \
	fi; \
	exit $$code
