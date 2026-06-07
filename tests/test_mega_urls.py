from megaqueue.mega_urls import normalize, extract_folder_id, is_folder_url


# --- URL Normalization ---

def test_normalize_old_format():
    url = "https://mega.nz/#!abcdef!key123"
    assert normalize(url) == "abcdef#key123"


def test_normalize_new_format():
    url = "https://mega.nz/file/abcdef#key123"
    assert normalize(url) == "abcdef#key123"


def test_normalize_old_and_new_match():
    old = "https://mega.nz/#!abcdef!key123"
    new = "https://mega.nz/file/abcdef#key123"
    assert normalize(old) == normalize(new)


def test_normalize_folder_file_format():
    url = "https://mega.nz/#N!abcdef!key123###n=folderid"
    result = normalize(url)
    assert "folderid" not in result
    assert "abcdef" in result


def test_normalize_passthrough_unknown():
    url = "https://example.com/unknown"
    assert normalize(url) == url


# --- Folder ID Extraction ---

def test_extract_folder_id_from_folder_url():
    url = "https://mega.nz/folder/LAlWVZbQ#HUccRplmJSvCF-9bOuyFJg"
    assert extract_folder_id(url) == "LAlWVZbQ"


def test_extract_folder_id_from_per_file_url():
    url = "https://mega.nz/#N!HIkkFLQZ!9lZBceIU9TmzfU4QrMoPbjVsQsLACzxMHt_wy7CI4bg###n=LAlWVZbQ"
    assert extract_folder_id(url) == "LAlWVZbQ"


def test_extract_folder_id_plain_file_url_returns_none():
    url = "https://mega.nz/file/abc123#key456"
    assert extract_folder_id(url) is None


def test_extract_folder_id_empty_string_returns_none():
    assert extract_folder_id("") is None


def test_extract_folder_id_from_old_format_folder_url():
    url = "https://mega.nz/#F!abc!keypart"
    assert extract_folder_id(url) == "abc"


# --- Folder URL Detection ---

def test_is_folder_url_new_format():
    assert is_folder_url("https://mega.nz/folder/abc#xyz") is True


def test_is_folder_url_old_format():
    assert is_folder_url("https://mega.nz/#F!abc!xyz") is True


def test_is_folder_url_new_file_format():
    assert is_folder_url("https://mega.nz/file/abc#xyz") is False


def test_is_folder_url_old_file_format():
    assert is_folder_url("https://mega.nz/#!abc!xyz") is False
