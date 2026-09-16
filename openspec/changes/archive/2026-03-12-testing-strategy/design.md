## Context

MegaQueue is a hobby project with no automated tests. The development workflow requires committing, pushing to GitHub, pulling on the NUC, and manually verifying — a cycle that takes minutes per iteration. The codebase has clean module boundaries (worker, organizer, megabasterd_client, models, routes, notifications) that are well-suited to unit testing. External dependencies (megabasterd API, filesystem, ntfy.sh, SQLite) can be mocked or replaced with in-memory equivalents.

## Goals / Non-Goals

**Goals:**
- Fast local test suite (`pytest` runs in seconds) that catches logic bugs before deployment
- Tests that Claude Code can run inline during development to verify changes
- Coverage of the highest-risk modules: worker polling/status sync, file organizer routing, URL normalization
- Simple fixtures that represent real-world scenarios (single file, multi-file, folders, archives, failures)
- Low maintenance burden — tests should not break when unrelated code changes

**Non-Goals:**
- 100% code coverage — focus on logic-heavy code, skip trivial getters/template rendering
- End-to-end browser testing (Selenium, Playwright) — overkill for a hobby project
- Testing megabasterd Java code — out of scope, treat its API as a boundary
- Performance/load testing
- Testing the NUC deployment itself (NSSM, Cloudflare tunnel)

## Decisions

### 1. pytest as test framework
**Choice**: pytest over unittest
**Rationale**: pytest has simpler syntax (plain functions + assert), excellent fixture system, and is the Python community standard. No need for class-based test boilerplate.

### 2. In-memory SQLite for database tests
**Choice**: Use SQLAlchemy's `sqlite:///:memory:` for test database
**Rationale**: Real SQLite with in-memory storage tests actual SQL behavior without touching disk. No mocking the ORM — tests exercise real queries. Fast setup/teardown per test.

### 3. Mock megabasterd API at the HTTP level
**Choice**: Mock `requests` responses in `megabasterd_client` tests, not the client itself
**Rationale**: Testing the client's HTTP handling catches serialization bugs. For worker tests, mock the client module to isolate worker logic. Two layers of testing.

### 4. Mock filesystem operations in organizer tests
**Choice**: Use `tmp_path` (pytest built-in) for real filesystem operations in a temp directory
**Rationale**: The organizer does real file moves and archive extraction. Using actual temp files catches path-handling bugs that mocks would miss. `tmp_path` auto-cleans after each test.

### 5. Test directory structure
```
megaqueue/
├── tests/
│   ├── conftest.py          # Shared fixtures (app, db, client mocks)
│   ├── test_models.py       # Model creation, relationships, computed properties
│   ├── test_megabasterd_client.py  # API client HTTP handling
│   ├── test_worker.py       # Polling logic, status sync, state transitions
│   ├── test_organizer.py    # File routing, archive extraction, cleanup
│   ├── test_routes.py       # Flask route responses, form handling
│   └── test_notifications.py # Notification formatting and sending
├── requirements-dev.txt      # pytest, pytest-cov, responses
```

### 6. CLAUDE.md for agent instructions
**Choice**: Add a `megaqueue/CLAUDE.md` with testing workflow instructions
**Rationale**: Claude agents read `CLAUDE.md` automatically at the start of every conversation. This is the right place to tell agents: (1) always run `pytest` after making changes, (2) add/update tests when modifying or adding functionality, (3) how to run tests, and (4) the testing conventions to follow (fixture patterns, mocking approach). Without this, agents won't know tests exist or that they're expected to maintain them.

### 7. Dev dependencies in separate file
**Choice**: `requirements-dev.txt` that includes `-r requirements.txt`
**Rationale**: Keeps production dependencies clean. Dev deps are only needed locally, never on the NUC.

### 8. Use `responses` library for HTTP mocking
**Choice**: `responses` over `unittest.mock.patch` for requests
**Rationale**: Purpose-built for mocking `requests` library. Declarative API for registering mock responses. Catches unmatched requests automatically.

## Risks / Trade-offs

- **[Risk] Tests pass but NUC fails due to environment differences (Windows paths, permissions)** → Mitigate by using `pathlib.Path` in tests and organizer code; add a few path-format assertions. Accept that some environment issues will still require NUC testing.
- **[Risk] Mocked megabasterd responses drift from actual API** → Mitigate by basing fixtures on real captured responses. Keep fixture data in a clear format that's easy to compare with live responses.
- **[Risk] Test maintenance burden grows** → Mitigate by testing behavior not implementation. Test public interfaces, not internal helper functions. Keep fixture count small.
