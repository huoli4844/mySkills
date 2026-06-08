# Task: Fix domain-book-wiki test suite — P0

## Context
- Skills dir: /Users/huoli4844/.hermes/skills/research/domain-book-wiki/scripts
- Tests dir: /Users/huoli4844/.hermes/skills/research/domain-book-wiki/scripts/tests
- Python: python3.12 (3.11.11)
- PYTHONPATH: tests/conftest.py adds scripts/ to sys.path

## Current state
- 421 passed, 20 failed, 10 skipped, 336 ERRORS
- Major error: 336 "ValueError: I/O operation on closed file" in test_yaml_gen.py and test_wikilink_resolution.py
- Major failure: test_dag_pipeline.py — mocks `dag_pipeline` module (was split into dag_pipeline_done/ops/run)
- Major failure: test_dag_quality.py — imports from dag_utils (shim exists but some test logic wrong)

## What to fix

### Fix 1: test_yaml_gen.py — "I/O operation on closed file" (336 errors)
Root cause: conftest.py has a session-scoped fixture `_ensure_fixture_wiki` that opens files. test_yaml_gen.py opens template files during collection (outside fixture), but conftest's `_reset_config_singleton` or `_reset_log_utils` autouse fixtures close file handles between tests.

Fix: Move the file-opening logic in test_yaml_gen.py into test functions (not class/module level), or add a proper fixture.

### Fix 2: test_dag_pipeline.py — mock `dag_pipeline` module (10+ failures)
Root cause: `unittest.mock.patch('dag_pipeline.xxx')` — dag_pipeline.py was split 3 ways: dag_pipeline_done.py, dag_pipeline_ops.py, dag_pipeline_run.py

Fix: Change ALL `dag_pipeline.xxx` mock targets to `dag_pipeline_run.xxx`.

### Fix 3: test_dag_quality.py — imports from dag_utils (5+ failures)
Root cause: dag_utils.py exists as a shim but some symbols may be missing or incorrectly re-exported.

Fix: Verify dag_utils.py exports everything test_dag_quality.py needs. If missing, add the re-export.

### Fix 4: test_wikilink_resolution.py — "I/O operation on closed file" (5+ errors)
Root cause: Similar fixture lifecycle issue as test_yaml_gen.py.

Fix: Move file operations into test functions or fixtures.

## Acceptance criteria
- [ ] `cd /Users/huoli4844/.hermes/skills/research/domain-book-wiki/scripts && python3.12 -m pytest tests/ --tb=short -q` shows ≤20 failures (down from 356 failures+errors)
- [ ] Backward compatible — no changes to production code, only test files
- [ ] Each fix is in a separate commit-worthy change

## Constraints
- Python 3.12 syntax OK (environment is 3.11.11)
- Do NOT modify conftest.py session-scoped fixtures
- Keep backward compatibility — production code unchanged
