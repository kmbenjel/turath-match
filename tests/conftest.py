from __future__ import annotations

from pathlib import Path

import pytest

from turath_match.models import FileRef, Record
from turath_match.net import Http

FIX = Path(__file__).parent / "fixtures"


def R(title: str, author: str = "", scheme: str = "t", rid: str | None = None, **kw) -> Record:
    return Record(scheme, rid or title, title, author, **kw)


class FakeTransport:
    """Answers requests from recorded fixture files; records every URL asked."""

    def __init__(self, routes: dict[str, str | bytes | Exception]):
        self.routes, self.calls = routes, []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> bytes:
        self.calls.append((url, headers))
        for key, val in self.routes.items():
            if key in url:
                if isinstance(val, Exception):
                    raise val
                return val if isinstance(val, bytes) else (FIX / val).read_bytes()
        raise OSError(f"no fixture for {url}")


@pytest.fixture
def fake_http(tmp_path):
    def make(routes):
        t = FakeTransport(routes)
        return Http(tmp_path / "cache", min_interval=0, transport=t), t

    return make


@pytest.fixture
def files():
    def make(*sizes: int) -> list[FileRef]:
        return [FileRef(name=f"v{i + 1:02d}.pdf", size=s) for i, s in enumerate(sizes)]

    return make
