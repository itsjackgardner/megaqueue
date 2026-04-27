import json

import responses
import pytest
from requests.exceptions import ConnectionError

from megaqueue.megabasterd_client import MegabasterdClient


@pytest.fixture
def mb_client():
    return MegabasterdClient(base_url="http://localhost:9999")


@responses.activate
def test_status_returns_parsed_response(mb_client):
    responses.get(
        "http://localhost:9999/status",
        json={
            "running": True,
            "downloads": [
                {"url": "mega.nz/file/a#1", "name": "file1.mkv", "finished": False},
                {"url": "mega.nz/file/b#2", "name": "file2.mkv", "finished": True},
            ],
        },
    )

    result = mb_client.status()
    assert result["running"] is True
    assert len(result["downloads"]) == 2


@responses.activate
def test_start_sends_urls(mb_client):
    responses.post("http://localhost:9999/start", json={"ok": True})

    result = mb_client.start(["mega.nz/file/abc#key1", "mega.nz/file/def#key2"])

    assert result == {"ok": True}
    body = json.loads(responses.calls[0].request.body)
    assert "abc#key1" in body["urls"]
    assert "def#key2" in body["urls"]


@responses.activate
def test_start_accepts_string(mb_client):
    responses.post("http://localhost:9999/start", json={"ok": True})

    mb_client.start("mega.nz/file/abc#key1\nmega.nz/file/def#key2")

    body = json.loads(responses.calls[0].request.body)
    assert "abc#key1" in body["urls"]


@responses.activate
def test_stop(mb_client):
    responses.post("http://localhost:9999/stop", json={"ok": True})

    result = mb_client.stop("mega.nz/file/abc#key", delete=True)
    assert result == {"ok": True}


@responses.activate
def test_pause(mb_client):
    responses.post("http://localhost:9999/pause", json={"ok": True})
    assert mb_client.pause() == {"ok": True}


@responses.activate
def test_resume(mb_client):
    responses.post("http://localhost:9999/resume", json={"ok": True})
    assert mb_client.resume() == {"ok": True}


@responses.activate
def test_clear509(mb_client):
    responses.post("http://localhost:9999/clear509", json={"ok": True})
    assert mb_client.clear509() == {"ok": True}


@responses.activate
def test_rename(mb_client):
    responses.post("http://localhost:9999/rename", json={"ok": True})
    result = mb_client.rename("mega.nz/file/abc#key", "new_name.mkv")
    assert result == {"ok": True}


@responses.activate
def test_is_reachable_true(mb_client):
    responses.get("http://localhost:9999/status", json={"running": True})
    assert mb_client.is_reachable() is True


@responses.activate
def test_is_reachable_false_on_connection_error(mb_client):
    responses.get("http://localhost:9999/status", body=ConnectionError("refused"))
    assert mb_client.is_reachable() is False


@responses.activate
def test_connection_error_raises(mb_client):
    responses.get("http://localhost:9999/status", body=ConnectionError("refused"))
    with pytest.raises(ConnectionError):
        mb_client.status()


@responses.activate
def test_http_error_raises(mb_client):
    responses.get("http://localhost:9999/status", status=500)
    with pytest.raises(Exception):
        mb_client.status()
