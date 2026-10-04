import httpx
import pytest

from difm import AsyncClient


@pytest.mark.asyncio
async def test_async_stations_and_stream_resolution():
    stations = [{"id": 1, "key": "trance", "name": "Trance"}]

    async def handler(request):
        if request.url.path == "/v1/di/channels":
            return httpx.Response(200, json=stations)
        if request.url.host == "listen.di.test":
            return httpx.Response(
                200,
                text="[playlist]\nFile1=https://stream.example/trance\n",
            )
        raise AssertionError(request.url)

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(
        base_url="https://api.audioaddict.test/v1",
        transport=transport,
        follow_redirects=True,
    )
    client = AsyncClient(
        listen_key="abc",
        api_base="https://api.audioaddict.test/v1",
        listen_host="https://listen.di.test",
        http=http,
    )

    assert (await client.stations())[0].key == "trance"
    assert await client.stream_url("trance") == "https://stream.example/trance"
    await http.aclose()


@pytest.mark.asyncio
async def test_async_favorites_use_current_url_and_legacy_fallback():
    stations = [
        {"id": 1, "key": "trance", "name": "Trance"},
        {"id": 2, "key": "ambient", "name": "Ambient"},
    ]
    attempts = []

    async def handler(request):
        if request.url.path == "/v1/di/channels":
            return httpx.Response(200, json=stations)
        if request.url.host == "listen.di.test":
            attempts.append(str(request.url))
            if len(attempts) == 1:
                return httpx.Response(406)
            return httpx.Response(
                200,
                text=(
                    "[playlist]\n"
                    "File1=https://edge.example/3rdparty_di_trance_aac\n"
                    "Title1=DI.FM - Trance\n"
                    "File2=https://edge.example/di_ambient_mp3\n"
                    "Title2=DI.FM - Ambient\n"
                ),
            )
        raise AssertionError(request.url)

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(
        base_url="https://api.audioaddict.test/v1",
        transport=transport,
        follow_redirects=True,
    )
    client = AsyncClient(
        listen_key="abc",
        api_base="https://api.audioaddict.test/v1",
        listen_host="https://listen.di.test",
        http=http,
    )

    favorites = await client.my_stations()
    assert [station.key for station in favorites] == ["trance", "ambient"]
    assert attempts == [
        "https://listen.di.test/premium/favorites.pls?listen_key=abc&download=1",
        "https://listen.di.test/premium_high/favorites.pls?listen_key=abc",
    ]
    await http.aclose()
