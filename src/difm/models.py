from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StreamQuality(StrEnum):
    """Friendly stream quality names mapped to DI.FM stream-list keys."""

    LOW = "premium_medium"
    MEDIUM = "premium"
    HIGH = "premium_high"
    PUBLIC = "public3"


class Station(BaseModel):
    """A DI.FM station/channel."""

    model_config = ConfigDict(extra="allow")

    id: int
    key: str
    name: str
    description: str | None = None
    description_short: str | None = None
    description_long: str | None = None
    network_id: int | None = None
    premium_id: int | None = None
    channel_director: str | None = None
    public: bool | None = None
    asset_url: Any | None = None
    banner_url: Any | None = None
    images: Any | None = None
    artists: list[Any] = Field(default_factory=list)
    similar_channels: list[Any] = Field(default_factory=list)
    channel_filter_ids: list[int] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class Favorite(BaseModel):
    """Favorite-station reference from the JSON API."""

    model_config = ConfigDict(extra="allow")

    channel_id: int
    position: int | None = None


class Track(BaseModel):
    """Track/history payload used by currently-playing endpoints."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    track_id: int | None = None
    channel_id: int | None = None
    title: str | None = None
    display_title: str | None = None
    artist: str | None = None
    display_artist: str | None = None
    length: float | None = None
    duration: float | None = None
    started: int | None = None
    start_time: str | None = None
    votes: Any | None = None
    art_url: Any | None = None
    images: Any | None = None


class NowPlaying(BaseModel):
    model_config = ConfigDict(extra="allow")

    channel_id: int
    channel_key: str
    track: Track | None = None


class Credentials(BaseModel):
    """Normalized credentials returned by either AudioAddict login style."""

    model_config = ConfigDict(extra="allow")

    user_id: int
    listen_key: str
    session_key: str | None = None
    api_key: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)

        # member_sessions:
        # {key, member_id, member: {listen_key, ...}}
        if "key" in data and "member_id" in data:
            member = data.get("member") or {}
            return {
                **data,
                "user_id": data["member_id"],
                "session_key": data["key"],
                "listen_key": member.get("listen_key", ""),
            }

        # members/authenticate:
        # {id, api_key, listen_key, ...}
        if "user_id" not in data and "id" in data:
            data["user_id"] = data["id"]
        return data


class PlaylistEntry(BaseModel):
    """One entry in a PLS/M3U playlist."""

    url: str
    title: str | None = None
    length: int | None = None
