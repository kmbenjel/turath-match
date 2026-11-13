"""Polite HTTP for the online adapters: a disk cache, one request per host per interval, retries with backoff.

Every response is cached under ``cache_dir`` by URL, so a second run makes no request at all and a run that
stopped half way resumes where it was. The User-Agent names the tool, never a person; set
``TURATH_MATCH_USER_AGENT`` to add your own contact if a service asks for one.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__

USER_AGENT = os.environ.get(
    "TURATH_MATCH_USER_AGENT", f"turath-match/{__version__} (catalog reconciliation tool)"
)

Transport = Callable[[str, dict[str, str], float], bytes]


def default_cache_dir() -> Path:
    base = os.environ.get("TURATH_MATCH_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "turath-match"
    )
    return Path(base)


def urllib_transport(url: str, headers: dict[str, str], timeout: float) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return bytes(resp.read())


class HttpError(RuntimeError):
    def __init__(self, url: str, code: int | None, msg: str):
        super().__init__(f"{url}: {code or ''} {msg}".strip())
        self.url, self.code = url, code


class Http:
    """A cached, rate-limited GET. ``transport`` is swappable: tests pass one that reads fixtures."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        min_interval: float = 1.0,
        retries: int = 4,
        timeout: float = 60.0,
        transport: Transport | None = None,
        offline: bool = False,
    ):
        self.cache = Path(cache_dir) if cache_dir else default_cache_dir()
        self.min_interval, self.retries, self.timeout = min_interval, retries, timeout
        self.transport = transport or urllib_transport
        self.offline = offline
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self.requests = 0

    def _path(self, url: str) -> Path:
        host = urllib.parse.urlsplit(url).netloc or "local"
        return self.cache / host / hashlib.sha1(url.encode()).hexdigest()

    def _wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._last.get(host, 0.0) + self.min_interval - now
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()

    def get(self, url: str, *, refresh: bool = False) -> bytes:
        p = self._path(url)
        if p.exists() and not refresh:
            return p.read_bytes()
        if self.offline:
            raise HttpError(url, None, "not in the cache and offline mode is on")
        host = urllib.parse.urlsplit(url).netloc
        last: Exception | None = None
        for attempt in range(self.retries):
            self._wait(host)
            try:
                self.requests += 1
                data = self.transport(url, {"User-Agent": USER_AGENT, "Accept": "*/*"}, self.timeout)
            except urllib.error.HTTPError as e:
                if e.code in (400, 401, 403, 404, 410):
                    raise HttpError(url, e.code, "refused") from e
                last = e
            except (OSError, TimeoutError) as e:
                last = e
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_suffix(".part")
                tmp.write_bytes(data)
                tmp.replace(p)
                return data
            time.sleep(min(30.0, 2.0 * (attempt + 1)) if self.min_interval > 0 else 0)
        raise HttpError(url, None, f"failed after {self.retries} attempts: {last}")

    def get_json(self, url: str, **kw: Any) -> Any:
        return json.loads(self.get(url, **kw).decode("utf-8"))
