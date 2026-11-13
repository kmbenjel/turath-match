import os

from turath_match import SizeIndex, find_duplicates, fingerprint, trace
from turath_match.dups import DuplicateGroup, full_hash, scan_sizes, windows
from turath_match.models import DIFFERENT, HASH, SAME, FileRef

from .conftest import R


def _src(*specs):
    return [R(t, a, scheme="archive", rid=t, files=[FileRef(n, s, md5=m)]) for t, a, n, s, m in specs]


def test_unique_size_traces(tmp_path):
    idx = SizeIndex(_src(("كليلة ودمنة", "ابن المقفع", "144704.pdf", 12_196_642, "")))
    lib = [R("kalila", files=[FileRef("kalila.pdf", 12_196_642)])]
    (m,) = trace(lib, idx)
    assert m.verdict == SAME and m.method == "exact_size" and m.score >= 0.9
    assert m.right.files[0].name == "144704.pdf"


def test_ambiguous_size_prefers_matching_title():
    idx = SizeIndex(
        _src(
            ("الأدب الصغير", "ابن المقفع", "a.pdf", 5_000_000, ""),
            ("كليلة ودمنة", "ابن المقفع", "b.pdf", 5_000_000, ""),
        )
    )
    (m,) = trace([R("كليلة ودمنة", "عبد الله بن المقفع", files=[FileRef("k.pdf", 5_000_000)])], idx)
    assert m.right.title == "كليلة ودمنة"
    assert any("share this size" in e.detail for e in m.evidence)
    assert m.score < 0.9


def test_tiny_files_are_weak_evidence():
    idx = SizeIndex(_src(("x", "", "x.pdf", 1000, "")))
    (m,) = trace([R("y", files=[FileRef("y.pdf", 1000)])], idx)
    assert m.score < 0.6


def test_hash_verification(tmp_path):
    p = tmp_path / "book.pdf"
    p.write_bytes(b"%PDF-1.4 " + b"x" * 200_000)
    import hashlib

    good = hashlib.md5(p.read_bytes()).hexdigest()
    size = p.stat().st_size
    lib = [R("book", files=[FileRef("book.pdf", size, path=str(p))])]
    (m,) = trace(lib, SizeIndex(_src(("book", "", "o.pdf", size, good))), verify=True)
    assert m.method == HASH and m.score == 1.0
    (m,) = trace(lib, SizeIndex(_src(("book", "", "o.pdf", size, "0" * 32))), verify=True)
    assert m.verdict == DIFFERENT


def test_windows_cover_start_quarters_end():
    w = windows(1_000_000, 65536)
    assert w[0] == 0 and w[-1] == 1_000_000 - 65536 and len(w) == 5
    assert windows(1000) == [0]


def _write(p, data):
    p.write_bytes(data)
    return str(p), len(data)


def test_duplicates_proven_and_near_misses_rejected(tmp_path):
    base = os.urandom(400_000)
    a = _write(tmp_path / "a.pdf", base)
    b = _write(tmp_path / "b.pdf", base)
    mid = bytearray(base)
    mid[200_000] ^= 0xFF  # one byte changed inside the 50 % window
    c = _write(tmp_path / "c.pdf", bytes(mid))
    elsewhere = bytearray(base)
    elsewhere[100] ^= 0xFF  # inside the first window
    d = _write(tmp_path / "d.pdf", bytes(elsewhere))
    e = _write(tmp_path / "e.pdf", os.urandom(1234))
    groups = find_duplicates([a, b, c, d, e])
    assert len(groups) == 1 and groups[0].paths == sorted([a[0], b[0]])
    deep = find_duplicates([a, b, c, d, e], deep=True)
    assert deep[0].method == "hash" and deep[0].fingerprint == full_hash(a[0])


def test_sampling_misses_changes_between_windows_but_deep_catches(tmp_path):
    base = os.urandom(1_000_000)
    a = _write(tmp_path / "a.pdf", base)
    gap = bytearray(base)
    gap[150_000] ^= 1  # between the 0 % and 25 % windows
    b = _write(tmp_path / "b.pdf", bytes(gap))
    assert len(find_duplicates([a, b])) == 1  # sampled proof: same
    assert find_duplicates([a, b], deep=True) == []  # full hash: different


def test_unreadable_file_is_never_a_duplicate(tmp_path):
    a = _write(tmp_path / "a.pdf", b"x" * 200_000)

    def reader(path, off, n):
        raise OSError("refused")

    assert fingerprint(a[0], a[1], reader).startswith("error:")
    assert find_duplicates([a, (str(tmp_path / "gone.pdf"), a[1])], reader) == []


def test_short_read_is_an_error(tmp_path):
    a = _write(tmp_path / "a.pdf", b"x" * 200_000)
    assert fingerprint(a[0], a[1], lambda p, o, n: b"x").startswith("error:")


def test_scan_sizes_and_group_dict(tmp_path):
    (tmp_path / "s").mkdir()
    _write(tmp_path / "s" / "a.pdf", b"1" * 10)
    _write(tmp_path / "notes.txt", b"2")
    assert [os.path.basename(p) for p, _ in scan_sizes(tmp_path)] == ["a.pdf"]
    assert DuplicateGroup(1, "f", ["x"]).to_dict()["method"] == "sampled_bytes"
