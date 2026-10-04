"""DI.FM / AudioAddict Python client."""

from .async_client import AsyncClient
from .client import Client
from .errors import DIFMAuthError, DIFMError, DIFMHTTPError, DIFMPlaylistError
from .models import (
    Credentials,
    Favorite,
    NowPlaying,
    PlaylistEntry,
    Station,
    StreamQuality,
    Track,
)

__all__ = [
    "AsyncClient",
    "Client",
    "Credentials",
    "DIFMAuthError",
    "DIFMError",
    "DIFMHTTPError",
    "DIFMPlaylistError",
    "Favorite",
    "NowPlaying",
    "PlaylistEntry",
    "Station",
    "StreamQuality",
    "Track",
]
