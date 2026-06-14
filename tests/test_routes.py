from unittest.mock import patch, MagicMock

from megaqueue.models import Download, DownloadFile


@patch("megaqueue.app.start_worker")
def test_dashboard_returns_200(mock_worker, client, db_session):
    resp = client.get("/")
    assert resp.status_code == 200


@patch("megaqueue.app.start_worker")
def test_dashboard_lists_downloads(mock_worker, client, db_session, sample_download):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Test Movie" in resp.data


@patch("megaqueue.app.start_worker")
def test_add_download_form(mock_worker, client, db_session):
    resp = client.get("/download/add")
    assert resp.status_code == 200


@patch("megaqueue.app.start_worker")
@patch("megaqueue.app.mb_client")
def test_create_download_links_only(mock_mb, mock_worker, client, db_session):
    """Submit only accepts links; title/year/media_type are inferred later by guessit."""
    mock_mb.start = MagicMock()

    resp = client.post("/download", data={
        "links": "https://mega.nz/file/abc#key1\nhttps://mega.nz/file/def#key2",
    }, follow_redirects=False)

    assert resp.status_code == 302

    dl = db_session.query(Download).first()
    assert dl is not None
    assert dl.title is None
    assert dl.year is None
    assert dl.media_type is None
    assert dl.status == "queued"
    assert dl.metadata_confidence == "low"
    assert dl.metadata_source is None
    assert dl.downloading_since is None
    assert len(dl.files) == 2


@patch("megaqueue.app.start_worker")
@patch("megaqueue.app.mb_client")
def test_create_download_empty_links_redirects(mock_mb, mock_worker, client, db_session):
    resp = client.post("/download", data={
        "links": "",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert db_session.query(Download).count() == 0


@patch("megaqueue.app.start_worker")
def test_rename_needs_review_writes_metadata_and_unblocks(mock_worker, client, db_session):
    """Rename route writes user metadata and flips NEEDS_REVIEW -> DOWNLOADING."""
    dl = Download(status="needs_review", metadata_confidence="low")
    f1 = DownloadFile(url="u1", name="main.mkv", status="finished")
    f2 = DownloadFile(url="u2", name="trailer.mkv", status="finished")
    dl.files.extend([f1, f2])
    db_session.add(dl)
    db_session.commit()
    dl_id = dl.id
    f1_id = f1.id
    f2_id = f2.id

    resp = client.post(f"/download/{dl_id}/rename", data={
        "title": "Birth",
        "year": "2004",
        "media_type": "movie",
        "is_extra": [str(f2_id)],
    }, follow_redirects=False)
    assert resp.status_code == 302

    dl = db_session.get(Download, dl_id)
    assert dl.title == "Birth"
    assert dl.year == 2004
    assert dl.media_type == "movie"
    assert dl.status == "downloading"
    assert dl.metadata_source == "user"
    assert dl.metadata_confidence == "high"
    assert db_session.get(DownloadFile, f1_id).is_extra is False
    assert db_session.get(DownloadFile, f2_id).is_extra is True


@patch("megaqueue.app.start_worker")
def test_rename_downloading_writes_metadata_keeps_status(mock_worker, client, db_session):
    """Rename on a downloading download writes metadata but does not change status."""
    dl = Download(title="Old Title", media_type="movie", status="downloading",
                  metadata_confidence="high", metadata_source="guessit")
    dl.files.append(DownloadFile(url="u", status="downloading"))
    db_session.add(dl)
    db_session.commit()
    dl_id = dl.id

    resp = client.post(f"/download/{dl_id}/rename", data={
        "title": "New Title",
        "year": "2020",
        "media_type": "tv",
    }, follow_redirects=False)
    assert resp.status_code == 302

    dl = db_session.get(Download, dl_id)
    assert dl.title == "New Title"
    assert dl.year == 2020
    assert dl.media_type == "tv"
    assert dl.status == "downloading"
    assert dl.metadata_source == "user"
    assert dl.metadata_confidence == "high"


@patch("megaqueue.app.start_worker")
def test_rename_queued_writes_metadata_keeps_status(mock_worker, client, db_session):
    """Rename on a queued download writes metadata but does not change status."""
    dl = Download(status="queued", metadata_confidence="low")
    dl.files.append(DownloadFile(url="u", status="queued"))
    db_session.add(dl)
    db_session.commit()
    dl_id = dl.id

    resp = client.post(f"/download/{dl_id}/rename", data={
        "title": "My Movie",
        "year": "2024",
        "media_type": "movie",
    }, follow_redirects=False)
    assert resp.status_code == 302

    dl = db_session.get(Download, dl_id)
    assert dl.title == "My Movie"
    assert dl.year == 2024
    assert dl.media_type == "movie"
    assert dl.status == "queued"
    assert dl.metadata_source == "user"
    assert dl.metadata_confidence == "high"


@patch("megaqueue.app.start_worker")
def test_rename_rejected_for_terminal_statuses(mock_worker, client, db_session):
    """Rename is rejected for complete, failed, and cancelled downloads."""
    for status in ("complete", "failed", "cancelled"):
        dl = Download(title="Original", media_type="movie", status=status,
                      metadata_confidence="high")
        dl.files.append(DownloadFile(url="u", status="finished"))
        db_session.add(dl)
        db_session.commit()
        dl_id = dl.id

        resp = client.post(f"/download/{dl_id}/rename", data={
            "title": "Changed",
            "media_type": "movie",
        }, follow_redirects=False)
        assert resp.status_code == 302

        dl = db_session.get(Download, dl_id)
        assert dl.title == "Original"


@patch("megaqueue.app.start_worker")
def test_old_resolve_url_not_found(mock_worker, client, db_session):
    """The old /resolve URL no longer matches a route."""
    dl = Download(status="needs_review", metadata_confidence="low")
    dl.files.append(DownloadFile(url="u", status="finished"))
    db_session.add(dl)
    db_session.commit()

    resp = client.post(f"/download/{dl.id}/resolve", data={
        "title": "T", "media_type": "movie",
    }, follow_redirects=False)
    assert resp.status_code == 404


@patch("megaqueue.app.start_worker")
def test_download_detail(mock_worker, client, db_session, sample_download):
    resp = client.get(f"/download/{sample_download.id}")
    assert resp.status_code == 200
    assert b"Test Movie" in resp.data


@patch("megaqueue.app.start_worker")
def test_download_detail_missing_redirects(mock_worker, client, db_session):
    resp = client.get("/download/999", follow_redirects=False)
    assert resp.status_code == 302


@patch("megaqueue.app.start_worker")
def test_api_status_returns_json(mock_worker, client, db_session, sample_download):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "Test Movie"


@patch("megaqueue.app.start_worker")
def test_api_status_returns_leaf_files_for_folder_download(mock_worker, client, db_session):
    """Folder downloads return child file entries in API, not parent folder record."""
    dl = Download(title="Show", year=2024, media_type="tv", status="downloading")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key", status="downloading")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    child1 = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                          url="u1", name="ep01.mkv", status="finished")
    child2 = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                          url="u2", name="ep02.mkv", status="downloading")
    db_session.add_all([child1, child2])
    db_session.commit()

    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    files = data[0]["files"]
    assert len(files) == 2
    names = {f["name"] for f in files}
    assert "ep01.mkv" in names
    assert "ep02.mkv" in names


@patch("megaqueue.app.start_worker")
@patch("megaqueue.app.mb_client")
def test_cancel_download(mock_mb, mock_worker, client, db_session, sample_download):
    mock_mb.stop = MagicMock()
    dl_id = sample_download.id

    resp = client.post(f"/download/{dl_id}/cancel", follow_redirects=False)
    assert resp.status_code == 302

    dl = db_session.get(Download, dl_id)
    assert dl.status == "cancelled"


@patch("megaqueue.app.start_worker")
def test_delete_download(mock_worker, client, db_session, sample_download):
    dl_id = sample_download.id
    resp = client.post(f"/download/{dl_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert db_session.get(Download, dl_id) is None
