from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote, urlparse

import httpx

from .errors import DIFMAuthError, DIFMHTTPError
from .models import Credentials, Station, StreamQuality

API_BASE = "https://api.audioaddict.com/v1"
LISTEN_HOST = "https://listen.di.fm"
NETWORK = "di"

# Public credentials used by AudioAddict clients for the member_sessions endpoint.
_APP_AUTH = httpx.BasicAuth("streams", "diradio")


def normalize_quality(value: StreamQuality | str) -> str:
    if isinstance(value, StreamQuality):
        return value.value
    aliases = {
        "low": StreamQuality.LOW.value,
        "medium": StreamQuality.MEDIUM.value,
        "high": StreamQuality.HIGH.value,
        "public": StreamQuality.PUBLIC.value,
    }
    return aliases.get(value, value)


def stream_playlist_url(
    station_key: str,
    listen_key: str,
    quality: StreamQuality | str = StreamQuality.HIGH,
    *,
    listen_host: str = LISTEN_HOST,
) -> str:
    streamlist = normalize_quality(quality)
    return (
        f"{listen_host.rstrip('/')}/{quote(streamlist)}/{quote(station_key)}.pls"
        f"?listen_key={quote(listen_key)}"
    )


def favorites_playlist_url(
    listen_key: str,
    *,
    listen_host: str = LISTEN_HOST,
    streamlist: str = "public3",
) -> str:
    return (
        f"{listen_host.rstrip('/')}/{quote(streamlist)}/favorites.pls"
        f"?listen_key={quote(listen_key)}"
    )


def station_key_from_url(url: str, candidates: Iterable[str]) -> str | None:
    path = urlparse(url).path.lower()
    haystack = f"/{path.strip('/')}/"
    matches = [key for key in candidates if f"/{key.lower()}" in haystack]
    if matches:
        return max(matches, key=len)
    tail = path.rsplit("/", 1)[-1]
    for suffix in (".pls", ".m3u", ".m3u8"):
        if tail.endswith(suffix):
            tail = tail[: -len(suffix)]
    return tail or None


def normalize_credentials(payload: dict) -> Credentials:
    return Credentials.model_validate(payload)


def raise_for_response(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        data = response.json()
        message = (
            data.get("error")
            or data.get("message")
            or data.get("detail")
            or response.text
        )
    except Exception:
        message = response.text or response.reason_phrase
    error_cls = (
        DIFMAuthError if response.status_code in {401, 403} else DIFMHTTPError
    )
    raise error_cls(
        response.status_code,
        str(message).strip(),
        url=str(response.request.url) if response.request else None,
    )


def parse_stations(payload: object) -> list[Station]:
    if isinstance(payload, dict):
        if "channels" in payload and isinstance(payload["channels"], list):
            payload = payload["channels"]
        else:
            payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("Expected station list from AudioAddict API")
    return [Station.model_validate(item) for item in payload]
