# di-py

A typed Python client for DI.FM / AudioAddict station metadata, favorites, and authenticated stream URLs.

This library intentionally does **not** play audio. Its main job is to let a subscriber:

- fetch all DI.FM stations;
- fetch "my stations" / favorites;
- work with only a DI.FM listen key for read-only favorites and streams;
- authenticate with email/password when richer account access is needed;
- add/remove favorites when authenticated through the JSON API;
- build stable authenticated PLS URLs;
- resolve PLS/M3U playlists to the underlying audio stream URL;
- query currently-playing data, track history, channel filters, and events;
- access the mobile batch-update endpoint for lower-level/forward-compatible work;
- use either a synchronous or asynchronous client.

> [!WARNING]
> AudioAddict does not publish a supported public API for these endpoints. They are used by first-party/third-party clients and can change without notice. This project is not affiliated with DI.FM or AudioAddict.

## Installation

From the repository:

~~~bash
pip install git+https://github.com/robertely/di-py.git
~~~

For development:

~~~bash
git clone https://github.com/robertely/di-py
cd di-py
python -m pip install -e '.[dev]'
pytest
~~~

Python 3.11+ is supported.

## Quick start: listen key only

If you already have the subscriber listen key DI.FM gives you, no password is required for the core use case.

~~~python
from difm import Client

with Client(listen_key="YOUR_LISTEN_KEY") as di:
    stations = di.stations()
    favorites = di.my_stations()

    for station in favorites:
        print(station.name, station.key)

        # Stable authenticated playlist URL.
        playlist_url = di.stream_playlist_url(station)
        print("playlist:", playlist_url)

        # Fetch the PLS and return the first underlying audio URL.
        stream_url = di.stream_url(station)
        print("stream:", stream_url)
~~~

The asynchronous equivalent:

~~~python
import asyncio

from difm import AsyncClient


async def main():
    async with AsyncClient(listen_key="YOUR_LISTEN_KEY") as di:
        for station in await di.my_stations():
            print(station.name, await di.stream_url(station))


asyncio.run(main())
~~~

## Stations

~~~python
stations = di.stations()

trance = di.station("trance")
same_station = di.station(1)
~~~

A station is returned as a Pydantic model. Unknown fields from AudioAddict responses are preserved, so new API fields do not require an immediate library release.

Common fields include:

- id
- key
- name
- short/long descriptions
- network ID
- premium ID
- artwork/image data
- channel director
- similar channels
- filter IDs

## My stations / favorites

### Read-only, listen-key path

~~~python
di = Client(listen_key="...")
favorites = di.my_stations()
~~~

This fetches the DI.FM favorites PLS and correlates its entries with the current station catalog.

Aliases:

~~~python
di.favorite_stations()
di.my_stations()
~~~

### Authenticated JSON path

If a session/API key and user ID are present, favorite lookup automatically prefers the JSON endpoint:

~~~python
di = Client(
    session_key="...",
    listen_key="...",
    user_id=123,
)

favorites = di.favorite_stations()
~~~

Favorite references are also available directly:

~~~python
refs = di.favorite_refs()
~~~

And authenticated clients can mutate favorites:

~~~python
di.add_favorite(channel_id)
di.remove_favorite(channel_id)
~~~

## Authentication

Two known AudioAddict authentication styles are supported.

### Session login

This is the richer session flow used by current third-party client implementations:

~~~python
with Client() as di:
    credentials = di.login("you@example.com", "password")
    print(credentials.user_id)
    print(credentials.listen_key)
~~~

The returned session key is retained by the client and sent as an X-Session-Key header for authenticated API requests.

### Direct authentication

The older/direct authenticate endpoint can also be used:

~~~python
credentials = di.login(
    "you@example.com",
    "password",
    mode="direct",
)
~~~

This returns an API key rather than the member-session key. di-py sends that API key as a query parameter on authenticated operations when no session key is present.

No credentials are written to disk by this library.

## Stream URLs

### Stable playlist URL

~~~python
url = di.stream_playlist_url("trance")
~~~

With a listen key, the default high-quality URL has this general shape:

~~~text
https://listen.di.fm/premium_high/trance.pls?listen_key=...
~~~

### Resolve to the actual audio endpoint

~~~python
audio_url = di.stream_url("trance")
~~~

This fetches the PLS and returns its first File entry.

To skip network resolution and keep the stable playlist URL:

~~~python
playlist_url = di.stream_url("trance", resolve=False)
~~~

### Qualities

~~~python
from difm import StreamQuality

di.stream_url("trance", quality=StreamQuality.HIGH)
di.stream_url("trance", quality=StreamQuality.MEDIUM)
di.stream_url("trance", quality=StreamQuality.LOW)
~~~

The friendly quality mappings are:

| Friendly name | DI.FM stream-list key |
| --- | --- |
| high | premium_high |
| medium | premium |
| low | premium_medium |
| public | public3 |

Raw stream-list keys are also accepted as strings:

~~~python
di.stream_playlist_url("trance", quality="premium_low")
~~~

Get several at once:

~~~python
urls = di.stream_urls("trance")
~~~

## Other station-related APIs

~~~python
# Current track across channels
now = di.currently_playing()

# Recent tracks for a channel
history = di.track_history(channel_id)

# Channel grouping/filter, returned raw for forward compatibility
popular = di.channel_filter("popular")

# Upcoming events for a channel
events = di.events(channel_id)
~~~

## Batch update

AudioAddict's mobile batch-update endpoint can provide channel details, track history/current-track data, events, assets, and requested stream lists in one response.

Because that response has changed historically, di-py deliberately returns it as raw JSON:

~~~python
batch = di.batch_update(["premium_high", "public3"])
~~~

## Low-level escape hatch

Undocumented endpoints evolve. The clients expose a request helper so callers do not have to fork the package for every new endpoint:

~~~python
payload = di.request_json("GET", "/di/some_endpoint")
~~~

Authenticated request:

~~~python
payload = di.request_json(
    "GET",
    "/di/members/123/something",
    authenticated=True,
)
~~~

The asynchronous client has the same method and shape.

## Synchronous and asynchronous clients

The public APIs intentionally match:

~~~python
from difm import Client, AsyncClient
~~~

Use Client in normal synchronous programs and AsyncClient in asyncio applications.

## Error handling

~~~python
from difm import DIFMAuthError, DIFMHTTPError, DIFMPlaylistError
~~~

- DIFMHTTPError: non-success HTTP response
- DIFMAuthError: HTTP 401/403
- DIFMPlaylistError: malformed/empty/unsupported PLS or M3U data

## API stability

The DI.FM/AudioAddict endpoints are not an officially supported public developer API. In particular:

- endpoint paths may change;
- authentication flows may change;
- stream-list names/bitrates may change;
- response schemas may add/remove fields;
- the mobile batch-update schema should be considered unstable.

di-py therefore favors tolerant Pydantic models, raw-response escape hatches, and explicit stream-list strings.

## Sources and provenance

All external technical sources used while implementing this library are listed below. They were used as **behavioral/reference material**; di-py is an independent implementation and does not copy either project wholesale.

### 1. ukw2d/addictune-sdk

Repository: https://github.com/ukw2d/addictune-sdk  
License: MIT  
Reference revision observed during implementation: commit 97adbb4cfc62a4c1d749948555c320ecfedc9078

Files consulted:

- README.md
  - current high-level AudioAddict SDK behavior and endpoint coverage;
  - current example usage for station lookup, favorites, stream URLs, and resolution.
- addictune_sdk/api/channels.py
  - current channel endpoints;
  - JSON favorite endpoints;
  - PLS stream URL construction;
  - playlist resolution behavior.
- addictune_sdk/api/auth.py
  - member_sessions flow;
  - direct members/authenticate flow;
  - application Basic Auth used by the session endpoint.
- addictune_sdk/client.py
  - X-Session-Key session behavior;
  - separation of listen key from API/session authentication.
- addictune_sdk/models/auth.py
  - response shapes for member_sessions and members/authenticate.
- addictune_sdk/models/channel.py
  - contemporary station/channel response fields;
  - favorite and now-playing/track-history response shapes.
- addictune_sdk/models/network.py
  - AudioAddict listen-host convention;
  - friendly premium stream-list mappings.
- tests/integration/channels.py
  - evidence that the public channel endpoint returns current channel keys;
  - live-tested PLS URL shape;
  - favorite add/remove endpoint behavior.
- LICENSE
  - used only to verify/source attribution and license terms.

Project copyright remains with its authors under the MIT license.

### 2. GeertJohan/tune

Repository: https://github.com/GeertJohan/tune  
License: BSD 2-Clause  
Reference revision observed during implementation: commit 1c5219ff715125f6cdda2e97812c961a3db2a031

Files consulted:

- api-rev-5.html
  - historical reverse-engineered AudioAddict API documentation;
  - members/authenticate endpoint;
  - listen_key and api_key behavior;
  - favorites endpoints;
  - favorites PLS behavior;
  - mobile/batch_update endpoint and stream_set_key parameter;
  - channel-filter, event, track-history, and related endpoint families;
  - historical DI.FM stream-list names.
- README.md
  - project scope/history and confirmation that Tune implemented the AudioAddict API.
- LICENSE
  - used only to verify/source attribution and license terms.

Project copyright remains with Geert-Johan Riemer under the BSD 2-Clause license.

### 3. DI.FM / AudioAddict service behavior

The service endpoints referenced by both projects above include:

- api.audioaddict.com
- listen.di.fm

No official supported public developer API documentation was found/relied on for this implementation. Names such as DI.FM, Digitally Imported, and AudioAddict are trademarks of their respective owners.

## Why both sources?

The older Tune documentation is unusually complete about the historical API surface, stream lists, favorites, and batch-update structure. addictune-sdk is much newer and provides evidence of which endpoint shapes are still being used by a contemporary Python client.

Where the two sources differ, di-py generally follows the newer behavior and keeps a low-level escape hatch for compatibility work.

## Contributing

When adding or changing an endpoint:

1. add a mocked unit test;
2. avoid putting real credentials/listen keys into fixtures;
3. keep response models tolerant of extra fields;
4. update the **Sources and provenance** section if a new external reference is used;
5. document whether an endpoint is public, session-authenticated, API-key-authenticated, or listen-key-based.

## License

di-py itself is released under the MIT License. See LICENSE.

The MIT license for di-py does not change the licenses, copyrights, or trademarks of the external projects/services listed above.
