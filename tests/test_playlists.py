from difm.playlists import first_stream_url, parse_m3u, parse_pls


def test_parse_pls():
    text = """[playlist]
NumberOfEntries=2
File1=https://example.com/a
Title1=One
Length1=-1
File2=https://example.com/b
Title2=Two
Length2=-1
"""
    entries = parse_pls(text)
    assert [entry.url for entry in entries] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert entries[0].title == "One"
    assert first_stream_url(text, url="https://listen.di.fm/x.pls") == "https://example.com/a"


def test_parse_m3u():
    text = """#EXTM3U
#EXTINF:-1,One
https://example.com/a
https://example.com/b
"""
    entries = parse_m3u(text)
    assert entries[0].title == "One"
    assert entries[1].url == "https://example.com/b"
