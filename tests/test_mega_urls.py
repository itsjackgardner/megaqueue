import base64

from megaqueue.mega_urls import normalize, extract_folder_id, is_folder_url, maybe_decode_base64


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


# --- Base64 URL Decoding ---

def _b64(s):
    return base64.b64encode(s.encode()).decode()


def _b64url(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def test_decode_raw_url_passthrough():
    url = "https://mega.nz/file/abc#key"
    assert maybe_decode_base64(url) == url


def test_decode_standard_base64():
    url = "https://mega.nz/file/abc#key"
    assert maybe_decode_base64(_b64(url)) == url


def test_decode_urlsafe_base64():
    url = "https://mega.nz/file/abc#key"
    assert maybe_decode_base64(_b64url(url)) == url


def test_decode_double_encoded():
    url = "https://mega.nz/folder/abc#key"
    encoded = _b64(_b64(url))
    assert maybe_decode_base64(encoded) == url


def test_decode_missing_padding():
    url = "https://mega.nz/file/abc#key"
    encoded = _b64(url).rstrip("=")
    assert maybe_decode_base64(encoded) == url


def test_decode_non_decodable_returns_original():
    text = "not-a-url-or-base64!!!"
    assert maybe_decode_base64(text) == text


def test_decode_non_mega_url_returns_original():
    encoded = _b64("https://example.com")
    assert maybe_decode_base64(encoded) == encoded


def test_decode_old_format_url():
    url = "https://mega.nz/#!abc!key"
    assert maybe_decode_base64(_b64(url)) == url


def test_decode_folder_url():
    url = "https://mega.nz/folder/abc#key"
    assert maybe_decode_base64(_b64(url)) == url
