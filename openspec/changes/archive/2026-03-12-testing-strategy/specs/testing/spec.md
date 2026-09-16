## ADDED Requirements

### Requirement: Test infrastructure and configuration
The project SHALL include a pytest-based test suite at `megaqueue/tests/` with shared fixtures in `conftest.py`. A `requirements-dev.txt` file SHALL list test dependencies (`pytest`, `pytest-cov`, `responses`) and include production dependencies via `-r requirements.txt`. Running `pytest` from the `megaqueue/` directory SHALL execute all tests.

#### Scenario: Run full test suite
- **WHEN** developer runs `pytest` from the `megaqueue/` directory
- **THEN** all tests execute and report pass/fail results within 30 seconds

#### Scenario: Install dev dependencies
- **WHEN** developer runs `pip install -r requirements-dev.txt`
- **THEN** all test and production dependencies are installed

### Requirement: Database test fixtures
The test suite SHALL provide a fixture that creates an in-memory SQLite database with all tables initialized. Each test SHALL receive a clean database session. The fixture SHALL use SQLAlchemy's `sqlite:///:memory:` engine.

#### Scenario: Isolated database per test
- **WHEN** two tests both create a Download record with the same title
- **THEN** neither test sees the other's data

#### Scenario: Full schema available
- **WHEN** a test uses the database fixture
- **THEN** both `downloads` and `download_files` tables exist with all columns

### Requirement: Flask test client fixture
The test suite SHALL provide a Flask test client fixture configured with `TESTING=True` and CSRF disabled for test simplicity. The test client SHALL use the in-memory database fixture.

#### Scenario: Route testing without CSRF
- **WHEN** a test POSTs to a route using the test client
- **THEN** the request succeeds without a CSRF token

### Requirement: Model tests
Tests SHALL verify Download and DownloadFile model creation, relationships, computed properties (`progress_bytes`, `total_bytes`, `speed`, `links`, `file_paths`), and status field values.

#### Scenario: Download with multiple files computes aggregate progress
- **WHEN** a Download has two DownloadFiles with `progress_bytes` 50 and 100
- **THEN** `download.progress_bytes` returns 150

#### Scenario: Download file_paths filters completed files
- **WHEN** a Download has files with statuses "finished" (with `file_path` set) and "downloading" (no `file_path`)
- **THEN** `download.file_paths` returns only the finished file's path

#### Scenario: Download links extracts URLs from files
- **WHEN** a Download has three DownloadFiles with distinct URLs
- **THEN** `download.links` returns all three URLs

### Requirement: Megabasterd client tests
Tests SHALL verify the megabasterd HTTP client handles successful responses, connection errors, and timeout scenarios for all endpoints (`status`, `start`, `stop`, `pause`, `resume`, `clear509`, `is_reachable`). HTTP responses SHALL be mocked using the `responses` library.

#### Scenario: Status endpoint returns parsed download list
- **WHEN** megabasterd `/status` returns a JSON response with two downloads
- **THEN** `client.status()` returns the parsed dict with both downloads

#### Scenario: Start endpoint sends URLs correctly
- **WHEN** `client.start(["mega.nz/file/abc#key1", "mega.nz/file/def#key2"])` is called
- **THEN** a POST is sent to `/start` with newline-separated URLs in the body

#### Scenario: Connection error is handled gracefully
- **WHEN** megabasterd API is unreachable
- **THEN** `client.is_reachable()` returns False without raising an exception

### Requirement: Worker tests
Tests SHALL verify the worker's core logic: URL normalization, megabasterd-to-database file matching, status derivation, and download state transitions. The megabasterd client SHALL be mocked at the module level. Database operations SHALL use the in-memory database fixture.

#### Scenario: Normalize old-format MEGA URL
- **WHEN** `_normalize_mega_url` receives `https://mega.nz/#!abcdef!key123`
- **THEN** it returns a normalized form that matches the equivalent new-format URL

#### Scenario: Normalize new-format MEGA URL
- **WHEN** `_normalize_mega_url` receives `https://mega.nz/file/abcdef#key123`
- **THEN** it returns the same normalized form as the old-format equivalent

#### Scenario: All files finished triggers post-processing
- **WHEN** all DownloadFiles for a Download have status "finished"
- **THEN** the worker sets the Download status to "processing" and calls post-process

#### Scenario: File failure sets download to failed
- **WHEN** any DownloadFile has status "failed" and no files are still downloading
- **THEN** the worker sets the Download status to "failed" with an error message

#### Scenario: Grace period for missing downloads
- **WHEN** a Download has status "downloading" but megabasterd reports no matching entries
- **AND** the grace period (30 seconds) has elapsed since `downloading_since`
- **THEN** the worker sets the Download status to "failed"

### Requirement: Organizer tests
Tests SHALL verify file discovery, archive detection, movie routing, TV routing, and cleanup. Tests SHALL use `tmp_path` for real filesystem operations. Archive extraction SHALL be mocked (patool/7z dependency).

#### Scenario: Movie routed to correct directory
- **WHEN** a completed movie download titled "Inception" (year 2010) has a file `inception.mkv`
- **THEN** the organizer moves it to `{PLEX_MOVIES_DIR}/Inception (2010)/inception.mkv`

#### Scenario: TV episode routed to correct season directory
- **WHEN** a completed TV download titled "Breaking Bad" has a file `breaking.bad.S02E05.mkv`
- **THEN** the organizer moves it to `{PLEX_TV_DIR}/Breaking Bad/Season 02/breaking.bad.S02E05.mkv`

#### Scenario: Archive files are detected
- **WHEN** files include `movie.rar`, `movie.r01`, `movie.zip`, `movie.7z`
- **THEN** `_is_archive` returns True for all of them

#### Scenario: Source directory cleaned up after organization
- **WHEN** all files from a download have been routed to their destinations
- **THEN** the source directory and any empty parent directories are removed

### Requirement: Route tests
Tests SHALL verify HTTP responses for key routes: dashboard (`GET /`), add download form (`GET /download/add`), create download (`POST /download`), download detail (`GET /download/<id>`), and status API (`GET /api/status`). The megabasterd client SHALL be mocked.

#### Scenario: Dashboard returns 200 with downloads listed
- **WHEN** the database contains two downloads
- **AND** a GET request is made to `/`
- **THEN** the response status is 200 and contains both download titles

#### Scenario: Create download queues files with megabasterd
- **WHEN** a POST is made to `/download` with title "Test Movie", year 2024, media_type "movie", and two mega.nz URLs
- **THEN** a Download record is created with two DownloadFiles and megabasterd `start()` is called with the URLs

#### Scenario: Status API returns JSON
- **WHEN** a GET request is made to `/api/status`
- **THEN** the response is JSON with download status information

### Requirement: Claude agent testing instructions
A `megaqueue/CLAUDE.md` file SHALL document the testing workflow for Claude agents. It SHALL instruct agents to: (1) run `pytest` from `megaqueue/` after any code change, (2) add or update tests when modifying existing functionality or adding new functionality, (3) follow existing fixture and mocking conventions in `conftest.py`. The file SHALL include the test run command and a brief description of the test structure.

#### Scenario: Agent reads CLAUDE.md and knows to run tests
- **WHEN** a Claude agent starts a conversation involving megaqueue code changes
- **THEN** it reads `megaqueue/CLAUDE.md` and knows to run `cd megaqueue && pytest` to verify changes

#### Scenario: Agent adds tests for new functionality
- **WHEN** a Claude agent adds a new feature (e.g., a new route or worker behavior)
- **THEN** it also creates corresponding tests following the patterns in the existing test suite

#### Scenario: Agent updates tests for modified functionality
- **WHEN** a Claude agent modifies existing behavior (e.g., changes organizer routing logic)
- **THEN** it updates the relevant tests to match the new behavior and verifies they pass

### Requirement: Notification tests
Tests SHALL verify that notification functions format messages correctly and call the ntfy.sh API with correct parameters. HTTP calls SHALL be mocked.

#### Scenario: Completion notification sends correct message
- **WHEN** `notify_completion` is called for a movie "Inception" (2024)
- **THEN** a POST is sent to the ntfy endpoint with the movie title in the message

#### Scenario: Failure notification sends with high priority
- **WHEN** `notify_failure` is called for a failed download
- **THEN** a POST is sent to the ntfy endpoint with `Priority: high` header
