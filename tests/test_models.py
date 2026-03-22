from models import Download, DownloadFile


def test_download_creation(db_session):
    dl = Download(title="Inception", year=2010, media_type="movie")
    db_session.add(dl)
    db_session.commit()

    assert dl.id is not None
    assert dl.title == "Inception"
    assert dl.year == 2010
    assert dl.media_type == "movie"
    assert dl.status == "queued"


def test_download_file_relationship(db_session):
    dl = Download(title="Test", media_type="movie")
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key1"))
    dl.files.append(DownloadFile(url="https://mega.nz/file/def#key2"))
    db_session.add(dl)
    db_session.commit()

    assert len(dl.files) == 2
    assert dl.files[0].download_id == dl.id


def test_cascade_delete(db_session):
    dl = Download(title="Test", media_type="movie")
    dl.files.append(DownloadFile(url="https://mega.nz/file/abc#key"))
    db_session.add(dl)
    db_session.commit()

    file_id = dl.files[0].id
    db_session.delete(dl)
    db_session.commit()

    assert db_session.get(DownloadFile, file_id) is None


def test_progress_bytes_aggregation(db_session):
    dl = Download(title="Test", media_type="movie")
    dl.files.append(DownloadFile(url="u1", progress_bytes=50, total_bytes=100))
    dl.files.append(DownloadFile(url="u2", progress_bytes=100, total_bytes=200))
    db_session.add(dl)
    db_session.commit()

    assert dl.progress_bytes == 150
    assert dl.total_bytes == 300


def test_speed_aggregation(db_session):
    dl = Download(title="Test", media_type="movie")
    dl.files.append(DownloadFile(url="u1", speed=1000))
    dl.files.append(DownloadFile(url="u2", speed=2000))
    db_session.add(dl)
    db_session.commit()

    assert dl.speed == 3000


def test_links_property(db_session):
    dl = Download(title="Test", media_type="movie")
    urls = ["https://mega.nz/file/a#1", "https://mega.nz/file/b#2", "https://mega.nz/file/c#3"]
    for url in urls:
        dl.files.append(DownloadFile(url=url))
    db_session.add(dl)
    db_session.commit()

    assert dl.links == urls


def test_file_paths_filters_completed(db_session):
    dl = Download(title="Test", media_type="movie")
    dl.files.append(DownloadFile(url="u1", status="finished", file_path="/dest/file1.mkv"))
    dl.files.append(DownloadFile(url="u2", status="downloading"))
    dl.files.append(DownloadFile(url="u3", status="finished", file_path="/dest/file2.mkv"))
    db_session.add(dl)
    db_session.commit()

    assert dl.file_paths == ["/dest/file1.mkv", "/dest/file2.mkv"]


def test_to_dict(db_session):
    dl = Download(title="Test", year=2024, media_type="movie")
    dl.files.append(DownloadFile(url="u1"))
    db_session.add(dl)
    db_session.commit()

    d = dl.to_dict()
    assert d["title"] == "Test"
    assert d["year"] == 2024
    assert len(d["files"]) == 1
    assert "progress_bytes" in d


# --- parent_id / children ---

def test_parent_id_cascade_delete(db_session):
    """Deleting a parent DownloadFile also deletes its children."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    child = DownloadFile(
        download_id=dl.id,
        parent_id=folder_df.id,
        url="https://mega.nz/#N!id1!k1###n=abc",
        name="ep01.mkv",
    )
    db_session.add(child)
    db_session.commit()
    child_id = child.id

    db_session.delete(folder_df)
    db_session.commit()

    assert db_session.get(DownloadFile, child_id) is None


def test_leaf_files_returns_children_not_parent(db_session):
    """leaf_files returns child records, not the parent folder record."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    child1 = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                          url="u1", name="ep01.mkv")
    child2 = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                          url="u2", name="ep02.mkv")
    db_session.add_all([child1, child2])
    db_session.commit()
    db_session.refresh(dl)

    leaf = dl.leaf_files
    assert len(leaf) == 2
    assert folder_df not in leaf
    assert child1 in leaf
    assert child2 in leaf


def test_leaf_files_falls_back_to_direct_files_before_expansion(db_session):
    """Before folder expansion, leaf_files returns the top-level folder record."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    leaf = dl.leaf_files
    assert leaf == [folder_df]


def test_links_returns_only_top_level_urls(db_session):
    """links property excludes child URLs (per-file from megabasterd folder splits)."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    child = DownloadFile(
        download_id=dl.id, parent_id=folder_df.id,
        url="https://mega.nz/#N!id1!k1###n=abc", name="ep01.mkv",
    )
    db_session.add(child)
    db_session.commit()
    db_session.refresh(dl)

    assert dl.links == ["https://mega.nz/folder/abc#key"]


def test_progress_bytes_aggregates_leaf_files_only(db_session):
    """progress_bytes uses leaf files, not the parent folder record."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key",
                             progress_bytes=999, total_bytes=999)
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    child1 = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                          url="u1", progress_bytes=300, total_bytes=500)
    child2 = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                          url="u2", progress_bytes=200, total_bytes=400)
    db_session.add_all([child1, child2])
    db_session.commit()
    db_session.refresh(dl)

    assert dl.progress_bytes == 500
    assert dl.total_bytes == 900


def test_to_dict_files_returns_leaf_files(db_session):
    """to_dict 'files' key contains leaf files (children), not parent folder record."""
    dl = Download(title="Show", media_type="tv")
    folder_df = DownloadFile(url="https://mega.nz/folder/abc#key")
    dl.files.append(folder_df)
    db_session.add(dl)
    db_session.commit()

    child = DownloadFile(download_id=dl.id, parent_id=folder_df.id,
                         url="u1", name="ep01.mkv")
    db_session.add(child)
    db_session.commit()
    db_session.refresh(dl)

    d = dl.to_dict()
    assert len(d["files"]) == 1
    assert d["files"][0]["name"] == "ep01.mkv"
