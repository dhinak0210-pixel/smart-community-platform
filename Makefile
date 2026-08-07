# ──────────────────────────────────────────────────────────────────────────────
# Smart Community Platform — Test Automation Makefile
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: install-test test test-unit test-integration test-agents test-e2e test-coverage test-fast test-verbose clean-test

PYTHON := $(shell if [ -f venv/bin/python3 ]; then echo "venv/bin/python3"; else which python3 || which python; fi)

# Install test dependencies
install-test:
	$(PYTHON) -m pip install pytest pytest-cov pytest-mock httpx factory-boy faker freezegun

# Run full test suite
test:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/ -v --tb=short -x

# Run only unit tests
test-unit:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/unit/ -v --tb=short -x

# Run only integration tests
test-integration:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/integration/ -v --tb=short -x

# Run only agent tests
test-agents:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/agents/ -v --tb=short -x

# Run only e2e tests
test-e2e:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/e2e/ -v --tb=short -x

# Run with coverage report
test-coverage:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/ -v --tb=short \
		--cov=backend \
		--cov-report=term-missing \
		--cov-report=html:backend/tests/htmlcov \
		--cov-fail-under=50

# Run fast tests only (exclude slow-marked tests)
test-fast:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/ -v --tb=short -x -m "not slow"

# Run with verbose output
test-verbose:
	PYTHONPATH=. $(PYTHON) -m pytest backend/tests/ -vvv --tb=long -x

# Clean test artifacts
clean-test:
	rm -rf backend/tests/htmlcov
	rm -rf backend/tests/.pytest_cache
	rm -rf .pytest_cache
	rm -f .coverage
	find . -type d -name __pycache__ | xargs rm -rf
