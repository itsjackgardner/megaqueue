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
def test_create_download(mock_mb, mock_worker, client, db_session):
    mock_mb.start = MagicMock()

    resp = client.post("/download", data={
        "title": "New Movie",
        "year": "2024",
        "media_type": "movie",
        "links": "https://mega.nz/file/abc#key1\nhttps://mega.nz/file/def#key2",
    }, follow_redirects=False)

    assert resp.status_code == 302  # redirect to index

    dl = db_session.query(Download).filter_by(title="New Movie").first()
    assert dl is not None
    assert dl.year == 2024
    assert dl.media_type == "movie"
    assert dl.status == "queued"
    assert dl.downloading_since is None  # not yet submitted to megabasterd
    assert len(dl.files) == 2


@patch("megaqueue.app.start_worker")
@patch("megaqueue.app.mb_client")
def test_create_download_empty_title_redirects(mock_mb, mock_worker, client, db_session):
    resp = client.post("/download", data={
        "title": "",
        "links": "https://mega.nz/file/abc#key",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert db_session.query(Download).count() == 0


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
