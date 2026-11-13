import urllib.error

import pytest

from turath_match.net import Http, HttpError, default_cache_dir


def test_cache_and_offline(fake_http, tmp_path):
    http, t = fake_http({"example.org/a": b"hello"})
    assert http.get("https://example.org/a") == b"hello"
    assert http.get("https://example.org/a") == b"hello"
    assert len(t.calls) == 1
    off = Http(tmp_path / "cache", offline=True)
    assert off.get("https://example.org/a") == b"hello"
    with pytest.raises(HttpError):
        off.get("https://example.org/b")


def test_refused_is_not_retried(fake_http):
    http, t = fake_http({"x": urllib.error.HTTPError("u", 404, "nf", {}, None)})
    with pytest.raises(HttpError) as e:
        http.get("https://example.org/x")
    assert e.value.code == 404 and len(t.calls) == 1


def test_transient_errors_retry(tmp_path):
    seq = [OSError("reset"), urllib.error.HTTPError("u", 503, "busy", {}, None), b'{"ok": 1}']

    def transport(url, headers, timeout):
        v = seq.pop(0)
        if isinstance(v, Exception):
            raise v
        return v

    http = Http(tmp_path, min_interval=0, transport=transport)
    assert http.get_json("https://example.org/j") == {"ok": 1}
    http2 = Http(
        tmp_path / "2", min_interval=0, retries=2, transport=lambda *a: (_ for _ in ()).throw(OSError("x"))
    )
    with pytest.raises(HttpError):
        http2.get("https://example.org/k")


def test_rate_limit_spaces_requests(tmp_path):
    import time

    stamps = []
    http = Http(
        tmp_path, min_interval=0.05, transport=lambda u, h, t: stamps.append(time.monotonic()) or b"x"
    )
    http.get("https://h.org/1")
    http.get("https://h.org/2")
    assert stamps[1] - stamps[0] >= 0.045


def test_cache_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TURATH_MATCH_CACHE", str(tmp_path))
    assert default_cache_dir() == tmp_path
