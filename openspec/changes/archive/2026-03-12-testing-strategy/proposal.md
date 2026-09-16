## Why

Development iteration requires committing, pushing, and manually testing on the NUC — a slow feedback loop that discourages experimentation. Automated tests would catch most issues locally before deployment, making development faster and more confident. As a hobby project, the testing strategy needs to be lightweight and practical, not enterprise-grade.

## What Changes

- Add a pytest-based test suite covering megaqueue's core logic (worker, organizer, megabasterd client, models, routes)
- Mock external dependencies (megabasterd API, filesystem, ntfy) so tests run locally without infrastructure
- Add a test runner configuration that Claude Code can invoke to verify changes during development
- Establish test fixtures for common scenarios (single file download, multi-file, folder links, archives, failures)
- Add a CI-friendly test command (`pytest`) that runs the full suite quickly
- Document the testing workflow in `megaqueue/CLAUDE.md` so Claude agents automatically run tests when making changes and add tests for new functionality

## Capabilities

### New Capabilities
- `testing`: Test infrastructure, fixtures, and test suite covering unit and integration tests for all megaqueue modules

### Modified Capabilities

_(none — testing is additive and does not change any existing spec-level requirements)_

## Impact

- New files: `tests/` directory with test modules, `conftest.py`, and fixtures
- New dev dependencies: `pytest`, `pytest-cov` (added to `requirements-dev.txt`)
- No changes to production code (tests only exercise existing interfaces)
- No changes to deployment or NUC setup
- New file: `megaqueue/CLAUDE.md` with testing instructions for Claude agents
