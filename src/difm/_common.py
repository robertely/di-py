from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote, unquote, urlencode, urlparse

import httpx

from .errors import DIFMAuthError, DIFMHTTPError
from .models import Credentials, PlaylistEntry, Station, StreamQuality

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
    streamlist: str = "premium",
    download: bool | None = None,
) -> str:
    """Build a favorites PLS URL.

    The current DI.FM listen host uses the premium favorites playlist with
    listen_key and download=1 query parameters. Older clients used
    premium_high or public3 variants, so callers can still request those
    stream-list names explicitly.
    """
    if download is None:
        download = streamlist == "premium"
    params = {"listen_key": listen_key}
    if download:
        params["download"] = "1"
    return (
        f"{listen_host.rstrip('/')}/{quote(streamlist, safe='')}/favorites.pls"
        f"?{urlencode(params)}"
    )


def favorites_playlist_urls(
    listen_key: str,
    *,
    listen_host: str = LISTEN_HOST,
) -> list[str]:
    """Return current and legacy favorites PLS URLs in preferred order."""
    base = listen_host.rstrip("/")
    encoded_key = quote(listen_key, safe="")
    urls = [
        favorites_playlist_url(
            listen_key,
            listen_host=listen_host,
            streamlist="premium",
            download=True,
        ),
        favorites_playlist_url(
            listen_key,
            listen_host=listen_host,
            streamlist="premium_high",
            download=False,
        ),
        f"{base}/premium_high/favorites.pls?{encoded_key}",
        favorites_playlist_url(
            listen_key,
            listen_host=listen_host,
            streamlist="public3",
            download=False,
        ),
        f"{base}/public3/favorites.pls?{encoded_key}",
    ]
    return list(dict.fromkeys(urls))


def station_key_from_url(
    url: str,
    candidates: Iterable[str],
    *,
    network: str | None = None,
) -> str | None:
    """Map a stream/playlist URL back to a known station key."""
    candidate_list = list(candidates)
    by_folded = {key.casefold(): key for key in candidate_list}
    path = unquote(urlparse(url).path)
    segments = [segment for segment in path.split("/") if segment]

    prefixes: tuple[str, ...] = ()
    if network:
        prefixes = (f"3rdparty_{network}_", f"{network}_")

    for segment in reversed(segments):
        value = segment
        for suffix in (".pls", ".m3u", ".m3u8"):
            if value.casefold().endswith(suffix):
                value = value[: -len(suffix)]
                break

        variants = [value]
        for prefix in prefixes:
            if value.casefold().startswith(prefix.casefold()):
                variants.append(value[len(prefix) :])

        for variant in variants:
            folded = variant.casefold()
            if folded in by_folded:
                return by_folded[folded]
            for suffix in ("_aac", "_mp3"):
                if folded.endswith(suffix):
                    without_codec = folded[: -len(suffix)]
                    if without_codec in by_folded:
                        return by_folded[without_codec]

    # Preserve the older path-substring behavior as a final compatibility
    # fallback for unusual historical stream mounts.
    path_folded = path.casefold()
    matches = [
        key
        for key in candidate_list
        if f"/{key.casefold()}" in f"/{path_folded.strip('/')}/"
    ]
    if matches:
        return max(matches, key=len)

    if not segments:
        return None
    return segments[-1] or None


def match_favorite_stations(
    entries: Iterable[PlaylistEntry],
    stations: Iterable[Station],
    *,
    network: str = NETWORK,
) -> list[Station]:
    """Correlate favorites PLS entries with the current station catalog."""
    station_list = list(stations)
    by_key = {station.key.casefold(): station for station in station_list}
    by_name = {station.name.casefold(): station for station in station_list}
    keys = [station.key for station in station_list]

    result: list[Station] = []
    seen: set[int] = set()

    for entry in entries:
        key = station_key_from_url(entry.url, keys, network=network)
        station = by_key.get(key.casefold()) if key else None

        if station is None and entry.title:
            title = entry.title.strip()
            title_candidates = [title]
            for separator in (" - ", " – ", " — "):
                if separator in title:
                    title_candidates.append(title.split(separator, 1)[1].strip())
            for title_candidate in title_candidates:
                station = by_name.get(title_candidate.casefold())
                if station is not None:
                    break

        if station is not None and station.id not in seen:
            result.append(station)
            seen.add(station.id)

    return result

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
