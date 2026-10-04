from difm._common import (
    favorites_playlist_url,
    favorites_playlist_urls,
    match_favorite_stations,
    station_key_from_url,
    stream_playlist_url,
)
from difm.models import PlaylistEntry, Station


def test_stream_playlist_url_encodes_station_and_listen_key():
    assert stream_playlist_url(
        "trance remix",
        "a+b/c?",
        listen_host="https://listen.di.test",
    ) == (
        "https://listen.di.test/premium_high/trance%20remix.pls"
        "?listen_key=a%2Bb%2Fc%3F"
    )


def test_favorites_playlist_url_defaults_to_current_premium_form():
    assert favorites_playlist_url(
        "a+b/c?",
        listen_host="https://listen.di.test",
    ) == (
        "https://listen.di.test/premium/favorites.pls"
        "?listen_key=a%2Bb%2Fc%3F&download=1"
    )


def test_favorites_playlist_urls_include_current_and_legacy_forms():
    urls = favorites_playlist_urls("abc", listen_host="https://listen.di.test")

    assert urls == [
        "https://listen.di.test/premium/favorites.pls?listen_key=abc&download=1",
        "https://listen.di.test/premium_high/favorites.pls?listen_key=abc",
        "https://listen.di.test/premium_high/favorites.pls?abc",
        "https://listen.di.test/public3/favorites.pls?listen_key=abc",
        "https://listen.di.test/public3/favorites.pls?abc",
    ]


def test_station_key_from_modern_and_legacy_mount_names():
    candidates = ["ambient", "trance"]

    assert station_key_from_url(
        "https://edge.example/ambient",
        candidates,
        network="di",
    ) == "ambient"
    assert station_key_from_url(
        "https://edge.example/3rdparty_di_ambient_aac",
        candidates,
        network="di",
    ) == "ambient"
    assert station_key_from_url(
        "https://edge.example/di_ambient_mp3",
        candidates,
        network="di",
    ) == "ambient"
    assert station_key_from_url(
        "https://listen.di.test/premium_high/trance.pls?listen_key=abc",
        candidates,
        network="di",
    ) == "trance"


def test_match_favorite_stations_handles_title_prefixes_and_duplicates():
    stations = [
        Station(id=1, key="trance", name="Trance"),
        Station(id=2, key="ambient", name="Ambient"),
    ]
    entries = [
        PlaylistEntry(
            url="https://edge.example/unmapped",
            title="DI.FM - Trance",
        ),
        PlaylistEntry(
            url="https://edge.example/3rdparty_di_ambient_aac",
            title="DI.FM - Ambient",
        ),
        PlaylistEntry(
            url="https://edge.example/di_ambient_mp3",
            title="Ambient",
        ),
    ]

    assert [
        station.key
        for station in match_favorite_stations(entries, stations, network="di")
    ] == ["trance", "ambient"]
