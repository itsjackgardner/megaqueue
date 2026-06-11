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
def test_resolve_writes_user_metadata_and_unblocks(mock_worker, client, db_session):
    """Resolve route writes user title/year/media_type and flips NEEDS_REVIEW -> PROCESSING."""
    dl = Download(status="needs_review", metadata_confidence="low")
    f1 = DownloadFile(url="u1", name="main.mkv", status="finished")
    f2 = DownloadFile(url="u2", name="trailer.mkv", status="finished")
    dl.files.extend([f1, f2])
    db_session.add(dl)
    db_session.commit()
    dl_id = dl.id
    f1_id = f1.id
    f2_id = f2.id

    resp = client.post(f"/download/{dl_id}/resolve", data={
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
    # Status is set back to DOWNLOADING — the next sync tick derives the right
    # state (PROCESSING when all files finished, runs post_process inline).
    # The route deliberately doesn't strand the download in PROCESSING.
    assert dl.status == "downloading"
    assert dl.metadata_source == "user"
    assert dl.metadata_confidence == "high"
    assert db_session.get(DownloadFile, f1_id).is_extra is False
    assert db_session.get(DownloadFile, f2_id).is_extra is True


@patch("megaqueue.app.start_worker")
def test_resolve_rejects_non_needs_review(mock_worker, client, db_session):
    """Resolve only works on NEEDS_REVIEW downloads."""
    dl = Download(title="Movie", media_type="movie", status="downloading",
                  metadata_confidence="high")
    dl.files.append(DownloadFile(url="u", status="downloading"))
    db_session.add(dl)
    db_session.commit()
    dl_id = dl.id

    resp = client.post(f"/download/{dl_id}/resolve", data={
        "title": "Other",
        "media_type": "movie",
    }, follow_redirects=False)
    assert resp.status_code == 302

    dl = db_session.get(Download, dl_id)
    assert dl.title == "Movie"  # unchanged
    assert dl.status == "downloading"


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
