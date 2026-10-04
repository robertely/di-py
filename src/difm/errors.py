class DIFMError(Exception):
    """Base exception for di-py."""


class DIFMHTTPError(DIFMError):
    """HTTP request failed."""

    def __init__(self, status_code: int, message: str, *, url: str | None = None):
        self.status_code = status_code
        self.url = url
        super().__init__(f"{status_code}: {message}" + (f" ({url})" if url else ""))


class DIFMAuthError(DIFMHTTPError):
    """Authentication or authorization failed."""


class DIFMPlaylistError(DIFMError):
    """A PLS/M3U playlist could not be parsed or resolved."""
