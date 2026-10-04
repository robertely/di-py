from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from ._common import (
    _APP_AUTH,
    API_BASE,
    LISTEN_HOST,
    NETWORK,
    favorites_playlist_url,
    favorites_playlist_urls,
    match_favorite_stations,
    normalize_credentials,
    parse_stations,
    raise_for_response,
    stream_playlist_url,
)
from .models import Credentials, Favorite, NowPlaying, Station, StreamQuality, Track
from .playlists import first_stream_url, parse_playlist


class AsyncClient:
    """Asynchronous DI.FM / AudioAddict client."""

    def __init__(
        self,
        *,
        listen_key: str | None = None,
        session_key: str | None = None,
        api_key: str | None = None,
        user_id: int | None = None,
        network: str = NETWORK,
        api_base: str = API_BASE,
        listen_host: str = LISTEN_HOST,
        timeout: float = 30.0,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.listen_key = listen_key
        self.session_key = session_key
        self.api_key = api_key
        self.user_id = user_id
        self.network = network
        self.api_base = api_base.rstrip("/")
        self.listen_host = listen_host.rstrip("/")
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            base_url=self.api_base,
            timeout=timeout,
            follow_redirects=True,
        )

    @classmethod
    def from_env(cls, prefix: str = "DIFM_") -> AsyncClient:
        """Create a client from DIFM_LISTEN_KEY/API_KEY/SESSION_KEY/USER_ID."""
        user_id = os.getenv(f"{prefix}USER_ID")
        return cls(
            listen_key=os.getenv(f"{prefix}LISTEN_KEY"),
            session_key=os.getenv(f"{prefix}SESSION_KEY"),
            api_key=os.getenv(f"{prefix}API_KEY"),
            user_id=int(user_id) if user_id else None,
        )

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        return {"X-Session-Key": self.session_key} if self.session_key else {}

    def _auth_params(self) -> dict[str, str]:
        return {"api_key": self.api_key} if self.api_key and not self.session_key else {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        params = dict(kwargs.pop("params", {}) or {})
        if authenticated:
            headers.update(self._headers())
            params.update(self._auth_params())
            if not headers.get("X-Session-Key") and "api_key" not in params:
                raise ValueError("This operation requires session_key or api_key")
        response = await self._http.request(
            method,
            path,
            headers=headers or None,
            params=params or None,
            **kwargs,
        )
        raise_for_response(response)
        return response

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = False,
        **kwargs: Any,
    ) -> Any:
        response = await self._request(method, path, authenticated=authenticated, **kwargs)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def login(
        self,
        email: str,
        password: str,
        *,
        mode: Literal["session", "direct"] = "session",
    ) -> Credentials:
        if mode == "session":
            response = await self._http.post(
                f"/{self.network}/member_sessions",
                json={"member_session": {"username": email, "password": password}},
                auth=_APP_AUTH,
            )
        elif mode == "direct":
            response = await self._http.post(
                f"/{self.network}/members/authenticate",
                data={"username": email, "password": password},
            )
        else:
            raise ValueError("mode must be 'session' or 'direct'")
        raise_for_response(response)
        credentials = normalize_credentials(response.json())
        self.user_id = credentials.user_id
        self.listen_key = credentials.listen_key
        self.session_key = credentials.session_key
        self.api_key = credentials.api_key
        return credentials

    async def stations(self) -> list[Station]:
        return parse_stations(
            (await self._request("GET", f"/{self.network}/channels")).json()
        )

    async def station(self, station: int | str) -> Station:
        if isinstance(station, int) or str(station).isdigit():
            response = await self._request(
                "GET", f"/{self.network}/channels/{int(station)}"
            )
            payload = response.json()
            if isinstance(payload, list):
                if not payload:
                    raise LookupError(f"Station {station!r} not found")
                payload = payload[0]
            return Station.model_validate(payload)
        key = str(station)
        for item in await self.stations():
            if item.key == key:
                return item
        raise LookupError(f"Station key {key!r} not found")

    async def currently_playing(self) -> list[NowPlaying]:
        payload = (
            await self._request("GET", f"/{self.network}/currently_playing")
        ).json()
        return [NowPlaying.model_validate(item) for item in payload]

    async def track_history(self, station_id: int) -> list[Track]:
        payload = (
            await self._request(
                "GET", f"/{self.network}/track_history/channel/{station_id}"
            )
        ).json()
        return [Track.model_validate(item) for item in payload]

    async def channel_filter(self, key: str) -> dict[str, Any]:
        return (
            await self._request(
                "GET", f"/{self.network}/channel_filters/key/{key}"
            )
        ).json()

    async def events(self, station_id: int) -> list[dict[str, Any]]:
        payload = (
            await self._request(
                "GET", f"/{self.network}/events/channel/{station_id}"
            )
        ).json()
        return list(payload)

    async def favorite_refs(self, user_id: int | None = None) -> list[Favorite]:
        resolved_user_id = user_id or self.user_id
        if resolved_user_id is None:
            raise ValueError("user_id is required for JSON favorites")
        payload = (
            await self._request(
                "GET",
                f"/{self.network}/members/{resolved_user_id}/favorites/channels",
                authenticated=True,
            )
        ).json()
        return [Favorite.model_validate(item) for item in payload]

    async def favorite_stations(self, user_id: int | None = None) -> list[Station]:
        all_stations = await self.stations()
        by_id = {station.id: station for station in all_stations}

        have_api_auth = bool(self.session_key or self.api_key)
        if (user_id or self.user_id) is not None and have_api_auth:
            refs = await self.favorite_refs(user_id)
            return [
                by_id[ref.channel_id]
                for ref in sorted(refs, key=lambda ref: ref.position or 0)
                if ref.channel_id in by_id
            ]

        if not self.listen_key:
            raise ValueError(
                "favorite_stations requires listen_key, or user_id plus API/session credentials"
            )

        response = None
        url = ""
        for candidate_url in favorites_playlist_urls(
            self.listen_key,
            listen_host=self.listen_host,
        ):
            response = await self._http.get(candidate_url)
            if response.is_success:
                url = candidate_url
                break

        if response is None or not response.is_success:
            if response is None:
                raise RuntimeError("No favorites playlist URL candidates were generated")
            raise_for_response(response)

        entries = parse_playlist(response.text, url=url)
        return match_favorite_stations(entries, all_stations, network=self.network)

    my_stations = favorite_stations

    async def add_favorite(
        self, station_id: int, user_id: int | None = None
    ) -> None:
        resolved_user_id = user_id or self.user_id
        if resolved_user_id is None:
            raise ValueError("user_id is required")
        await self._request(
            "POST",
            f"/{self.network}/members/{resolved_user_id}/favorites/channel/{station_id}",
            authenticated=True,
            json={"id": station_id},
        )

    async def remove_favorite(
        self, station_id: int, user_id: int | None = None
    ) -> None:
        resolved_user_id = user_id or self.user_id
        if resolved_user_id is None:
            raise ValueError("user_id is required")
        await self._request(
            "DELETE",
            f"/{self.network}/members/{resolved_user_id}/favorites/channel/{station_id}",
            authenticated=True,
        )

    def favorites_playlist_url(
        self,
        *,
        streamlist: str = "premium",
        download: bool | None = None,
    ) -> str:
        if not self.listen_key:
            raise ValueError("listen_key is required")
        return favorites_playlist_url(
            self.listen_key,
            listen_host=self.listen_host,
            streamlist=streamlist,
            download=download,
        )

    def stream_playlist_url(
        self,
        station: Station | str,
        *,
        quality: StreamQuality | str = StreamQuality.HIGH,
    ) -> str:
        if not self.listen_key:
            raise ValueError("listen_key is required")
        key = station.key if isinstance(station, Station) else str(station)
        return stream_playlist_url(
            key,
            self.listen_key,
            quality,
            listen_host=self.listen_host,
        )

    async def resolve_stream_url(self, playlist_url: str) -> str:
        suffix = urlparse(playlist_url).path.lower()
        if not suffix.endswith((".pls", ".m3u", ".m3u8")):
            return playlist_url
        response = await self._http.get(playlist_url)
        raise_for_response(response)
        return first_stream_url(response.text, url=playlist_url)

    async def stream_url(
        self,
        station: Station | str,
        *,
        quality: StreamQuality | str = StreamQuality.HIGH,
        resolve: bool = True,
    ) -> str:
        playlist = self.stream_playlist_url(station, quality=quality)
        if not resolve:
            return playlist
        return await self.resolve_stream_url(playlist)

    async def stream_urls(
        self,
        station: Station | str,
        *,
        qualities: Iterable[StreamQuality | str] = (
            StreamQuality.HIGH,
            StreamQuality.MEDIUM,
            StreamQuality.LOW,
        ),
        resolve: bool = False,
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for quality in qualities:
            name = quality.name.lower() if isinstance(quality, StreamQuality) else str(quality)
            result[name] = await self.stream_url(
                station, quality=quality, resolve=resolve
            )
        return result

    async def batch_update(self, streamlists: Iterable[str]) -> dict[str, Any]:
        payload = (
            await self._request(
                "GET",
                f"/{self.network}/mobile/batch_update",
                params={"stream_set_key": ",".join(streamlists)},
            )
        ).json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected batch_update response")
        return payload
