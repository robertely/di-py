from __future__ import annotations

from urllib.parse import urljoin

from .errors import DIFMPlaylistError
from .models import PlaylistEntry


def parse_pls(text: str, *, base_url: str | None = None) -> list[PlaylistEntry]:
    """Parse a PLS playlist into ordered entries."""
    rows: dict[int, dict[str, str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("[") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        lower = key.lower()

        for prefix, field in (("file", "url"), ("title", "title"), ("length", "length")):
            if lower.startswith(prefix):
                suffix = key[len(prefix):]
                if not suffix.isdigit():
                    break
                rows.setdefault(int(suffix), {})[field] = value
                break

    entries: list[PlaylistEntry] = []
    for index in sorted(rows):
        row = rows[index]
        if not row.get("url"):
            continue
        url = row["url"]
        if base_url:
            url = urljoin(base_url, url)
        length = None
        if row.get("length"):
            try:
                length = int(row["length"])
            except ValueError:
                pass
        entries.append(
            PlaylistEntry(url=url, title=row.get("title"), length=length)
        )
    return entries


def parse_m3u(text: str, *, base_url: str | None = None) -> list[PlaylistEntry]:
    """Parse M3U/M3U8, preserving EXTINF titles when present."""
    entries: list[PlaylistEntry] = []
    pending_title: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("#EXTINF:"):
            _, _, title = line.partition(",")
            pending_title = title.strip() or None
            continue
        if line.startswith("#"):
            continue
        url = urljoin(base_url, line) if base_url else line
        entries.append(PlaylistEntry(url=url, title=pending_title))
        pending_title = None
    return entries


def parse_playlist(text: str, *, url: str = "") -> list[PlaylistEntry]:
    """Parse a PLS or M3U playlist, inferred from URL/content."""
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".pls") or "[playlist]" in text.lower():
        return parse_pls(text, base_url=url or None)
    if lower.endswith((".m3u", ".m3u8")) or text.lstrip().startswith("#EXTM3U"):
        return parse_m3u(text, base_url=url or None)
    raise DIFMPlaylistError("Unsupported or unrecognized playlist format")


def first_stream_url(text: str, *, url: str = "") -> str:
    entries = parse_playlist(text, url=url)
    if not entries:
        raise DIFMPlaylistError("Playlist contains no stream URLs")
    return entries[0].url
