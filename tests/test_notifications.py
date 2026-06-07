import responses
from unittest.mock import MagicMock

from megaqueue.notifications import notify_completion, notify_failure, notify_needs_review


@responses.activate
def test_notify_completion_sends_message():
    responses.post("https://ntfy.sh/test-topic")

    dl = MagicMock(title="Inception", year=2010, error_message=None)
    notify_completion(dl)

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert b"Inception (2010)" in req.body
    assert req.headers["Title"] == "Download Complete"


@responses.activate
def test_notify_completion_without_year():
    responses.post("https://ntfy.sh/test-topic")

    dl = MagicMock(title="Untitled", year=None, error_message=None)
    notify_completion(dl)

    assert len(responses.calls) == 1
    assert b"Untitled" in responses.calls[0].request.body
    assert b"()" not in responses.calls[0].request.body


@responses.activate
def test_notify_failure_sends_high_priority():
    responses.post("https://ntfy.sh/test-topic")

    dl = MagicMock(title="Inception", year=2024, error_message="Connection lost")
    notify_failure(dl)

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Priority"] == "high"
    assert req.headers["Title"] == "Download Failed"
    assert b"Connection lost" in req.body


@responses.activate
def test_notify_failure_unknown_error():
    responses.post("https://ntfy.sh/test-topic")

    dl = MagicMock(title="Test", year=None, error_message=None)
    notify_failure(dl)

    assert len(responses.calls) == 1
    assert b"Unknown error" in responses.calls[0].request.body


@responses.activate
def test_notify_needs_review_movie_without_year():
    responses.post("https://ntfy.sh/test-topic")

    dl = MagicMock(title="Movie", year=None, media_type="movie")
    notify_needs_review(dl)

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Title"] == "Review needed"
    assert b"no year detected" in req.body


@responses.activate
def test_notify_needs_review_unresolved_title():
    responses.post("https://ntfy.sh/test-topic")

    dl = MagicMock(title=None, year=None, media_type=None)
    notify_needs_review(dl)

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert b"(unresolved)" in req.body
    assert b"no title detected" in req.body


@responses.activate
def test_notify_needs_review_swallows_send_failure(caplog):
    """ntfy failure logs but does not raise (status transition continues)."""
    responses.post("https://ntfy.sh/test-topic", status=500)

    dl = MagicMock(title="X", year=2024, media_type="movie")
    notify_needs_review(dl)  # should not raise
