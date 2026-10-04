import json

import httpx

from difm import Client, StreamQuality


STATIONS = [
    {"id": 1, "key": "trance", "name": "Trance"},
    {"id": 2, "key": "chillout", "name": "Chillout"},
]


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(
        base_url="https://api.audioaddict.test/v1",
        transport=transport,
        follow_redirects=True,
    )
    return Client(
        api_base="https://api.audioaddict.test/v1",
        listen_host="https://listen.di.test",
        http=http,
        **kwargs,
    )


def test_stations_and_station_lookup():
    def handler(request):
        if request.url.path == "/v1/di/channels":
            return httpx.Response(200, json=STATIONS)
        raise AssertionError(request.url)

    client = make_client(handler)
    assert [station.key for station in client.stations()] == ["trance", "chillout"]
    assert client.station("chillout").id == 2


def test_stream_playlist_url():
    client = make_client(lambda request: httpx.Response(500), listen_key="abc")
    assert (
        client.stream_playlist_url("trance", quality=StreamQuality.HIGH)
        == "https://listen.di.test/premium_high/trance.pls?listen_key=abc"
    )


def test_stream_url_resolves_pls():
    def handler(request):
        if request.url.host == "listen.di.test":
            return httpx.Response(
                200,
                text="[playlist]\nFile1=https://stream.example/trance\n",
            )
        raise AssertionError(request.url)

    client = make_client(handler, listen_key="abc")
    assert client.stream_url("trance") == "https://stream.example/trance"


def test_listen_key_only_favorites():
    def handler(request):
        if request.url.path == "/v1/di/channels":
            return httpx.Response(200, json=STATIONS)
        if request.url.host == "listen.di.test":
            return httpx.Response(
                200,
                text=(
                    "[playlist]\n"
                    "File1=https://edge.example/trance\n"
                    "Title1=Trance\n"
                    "File2=https://edge.example/chillout\n"
                    "Title2=Chillout\n"
                ),
            )
        raise AssertionError(request.url)

    client = make_client(handler, listen_key="abc")
    assert [station.key for station in client.my_stations()] == ["trance", "chillout"]


def test_json_favorites_use_session_header():
    seen = {}

    def handler(request):
        if request.url.path == "/v1/di/channels":
            return httpx.Response(200, json=STATIONS)
        if request.url.path == "/v1/di/members/7/favorites/channels":
            seen["session"] = request.headers.get("X-Session-Key")
            return httpx.Response(
                200,
                json=[
                    {"channel_id": 2, "position": 1},
                    {"channel_id": 1, "position": 2},
                ],
            )
        raise AssertionError(request.url)

    client = make_client(handler, session_key="sess", user_id=7, listen_key="abc")
    assert [station.key for station in client.favorite_stations()] == [
        "chillout",
        "trance",
    ]
    assert seen["session"] == "sess"


def test_direct_login_normalizes_credentials():
    def handler(request):
        if request.url.path == "/v1/di/members/authenticate":
            return httpx.Response(
                200,
                json={"id": 7, "api_key": "api", "listen_key": "listen"},
            )
        raise AssertionError(request.url)

    client = make_client(handler)
    credentials = client.login("a@example.com", "pw", mode="direct")
    assert credentials.user_id == 7
    assert client.api_key == "api"
    assert client.listen_key == "listen"


def test_batch_update():
    payload = {"streamlists": {"premium_high": {"channels": []}}}

    def handler(request):
        assert request.url.params["stream_set_key"] == "premium_high,public3"
        return httpx.Response(200, content=json.dumps(payload))

    client = make_client(handler)
    assert client.batch_update(["premium_high", "public3"]) == payload
