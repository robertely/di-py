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
