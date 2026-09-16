### Requirement: System decodes base64-encoded mega.nz URLs
The system SHALL provide a pure function `maybe_decode_base64(text)` in `mega_urls.py` that attempts to decode a base64-encoded string into a mega.nz URL. The function SHALL return the decoded mega.nz URL if successful, or the original text if decoding does not produce a valid mega.nz URL.

The function SHALL:
1. If the input already matches a mega.nz URL pattern, return it unchanged
2. Attempt standard base64 decoding (alphabet `A-Za-z0-9+/`)
3. If standard decoding fails or does not produce a mega.nz URL, attempt URL-safe base64 decoding (alphabet `A-Za-z0-9-_`)
4. If the first decode produces a string that is not a mega.nz URL, attempt a second round of decoding (to handle double-encoded input)
5. Accept input with or without `=` padding
6. Return the original text if no decoding round produces a valid mega.nz URL

A "valid mega.nz URL" is any string matching `https://mega.nz/` followed by a file, folder, or legacy path.

#### Scenario: Raw mega.nz URL passes through unchanged
- **WHEN** `maybe_decode_base64` is called with `https://mega.nz/file/abc#key`
- **THEN** it returns `https://mega.nz/file/abc#key` unchanged

#### Scenario: Standard base64-encoded URL is decoded
- **WHEN** `maybe_decode_base64` is called with the base64 encoding of `https://mega.nz/file/abc#key`
- **THEN** it returns `https://mega.nz/file/abc#key`

#### Scenario: URL-safe base64-encoded URL is decoded
- **WHEN** `maybe_decode_base64` is called with a URL-safe base64 encoding (using `-_` instead of `+/`)
- **THEN** it returns the decoded mega.nz URL

#### Scenario: Double-encoded URL is decoded
- **WHEN** `maybe_decode_base64` is called with text that is the base64 encoding of a base64 encoding of `https://mega.nz/folder/abc#key`
- **THEN** it returns `https://mega.nz/folder/abc#key`

#### Scenario: Input without padding is decoded
- **WHEN** `maybe_decode_base64` is called with a base64 string that has missing `=` padding
- **THEN** it still decodes successfully and returns the mega.nz URL

#### Scenario: Non-decodable input returns original text
- **WHEN** `maybe_decode_base64` is called with `not-a-url-or-base64`
- **THEN** it returns `not-a-url-or-base64` unchanged

#### Scenario: Base64 that decodes to non-mega URL returns original text
- **WHEN** `maybe_decode_base64` is called with the base64 encoding of `https://example.com`
- **THEN** it returns the original base64 string unchanged

#### Scenario: Old-format mega.nz URL is decoded from base64
- **WHEN** `maybe_decode_base64` is called with the base64 encoding of `https://mega.nz/#!abc!key`
- **THEN** it returns `https://mega.nz/#!abc!key`

#### Scenario: Folder URL is decoded from base64
- **WHEN** `maybe_decode_base64` is called with the base64 encoding of `https://mega.nz/folder/abc#key`
- **THEN** it returns `https://mega.nz/folder/abc#key`
