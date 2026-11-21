import json
from importlib import resources

from turath_match import reconcile
from turath_match.models import FileRef, Record
from turath_match.reconcile import load_decisions
from turath_match.report import to_html, to_markdown, write_reports
from turath_match.sources import open_source

from .conftest import R

DEMO = resources.files("turath_match") / "demo"


def _demo():
    lib = list(open_source(f"csv:{DEMO / 'library.csv'}").records())
    for r in lib:
        r.scheme = "library"
    wl = list(open_source(f"csv:{DEMO / 'wishlist.csv'}").records())
    for r in wl:
        r.scheme = "wishlist"
    copies = [
        *open_source(f"archive:{DEMO / 'archive.jsonl'}").records(),
        *open_source(f"openiti:{DEMO / 'openiti.tsv'}").records(),
    ]
    return lib, wl, copies


def test_demo_statuses():
    rec = reconcile(*_demo())
    st = {t.target.id: t.status for t in rec.targets}
    assert st == {
        "W01": "have",
        "W02": "other_edition",
        "W03": "related_only",
        "W04": "have",
        "W05": "have",
        "W06": "other_edition",
        "W07": "review",
        "W08": "have",
        "W09": "missing",
        "W10": "missing",
    }
    assert all(m.evidence for m in rec.matches)


def test_demo_byte_evidence_and_copies():
    rec = reconcile(*_demo())
    t = {t.target.id: t for t in rec.targets}
    assert t["W01"].provenance[0].right.key == "archive:AAlexandrina-164114"
    assert any("read from archive:AAlexandrina-144704" in e.detail for e in t["W05"].work.evidence)
    # al-Tusi's «تهافت الفلاسفة» is not al-Ghazali's, and its scan is told by its size
    assert t["W09"].status == "missing"
    assert all("Tussi" not in c.record.id for c in t["W09"].copies)
    assert rec.identified_by_bytes[0].right.id == "TahafutFalasifaAlaDinTussi"
    assert t["W02"].copies[0].record.key == "archive:elshandawily10111"
    assert [r.title for r in rec.unidentified] == ["مذكرات رحلة الحج"]


def test_partial_volumes_by_size(files):
    t = R("البيان والتبيين", "الجاحظ", scheme="cat", files=files(10_000_000, 11_000_000, 12_000_000))
    lib = R("bayan", scheme="library", files=files(10_000_000, 12_000_000))
    rec = reconcile([lib], [t])
    assert rec.targets[0].status == "partial"


def test_size_presence_despite_other_name(files):
    t = R("كليلة ودمنة", "ابن المقفع", scheme="cat", files=files(12_196_642))
    lib = R("scan 0042", scheme="library", files=files(12_196_642))
    assert reconcile([lib], [t]).targets[0].status == "have"


def test_madhhab_nisba_alone_is_not_an_author():
    t = R("الأم", "الشافعي", scheme="cat")
    lib = R("الأم", "محمد بن إدريس الشافعي", scheme="library")
    assert reconcile([lib], [t]).targets[0].status == "review"


def test_have_work_when_edition_unknown():
    t = R("المغني", "ابن قدامة", scheme="cat", publisher="دار هجر")
    lib = R("المغني", "موفق الدين ابن قدامة المقدسي", scheme="library")
    assert reconcile([lib], [t]).targets[0].status == "have_work"


def test_decisions_override(tmp_path):
    t = R("الرسالة", "محمد بن إدريس الشافعي", scheme="cat", rid="1")
    lib = R("الرسالة", "محمد", scheme="library", rid="L")
    assert reconcile([lib], [t]).targets[0].status == "review"
    p = tmp_path / "review.tsv"
    p.write_text("left\tright\tdecision\ncat:1\tlibrary:L\tsame\n", "utf-8")
    rec = reconcile([lib], [t], decisions=load_decisions(p))
    assert rec.targets[0].status == "have" and rec.targets[0].work.method == "manual"


def test_online_copies_are_searched_for_missing():
    class Online:
        def __init__(self):
            self.asked = []

        def search(self, title, author):
            self.asked.append((title, author))
            return [
                R(
                    "تهافت الفلاسفة",
                    "أبو حامد الغزالي",
                    scheme="archive",
                    rid="tahafut-1927",
                    files=[FileRef("t.pdf", 9_000_000)],
                    url="https://archive.org/details/tahafut-1927",
                )
            ]

    on = Online()
    rec = reconcile([], [R("تهافت الفلاسفة", "الغزالي", scheme="cat")], online=on)
    assert on.asked and rec.targets[0].copies[0].record.id == "tahafut-1927"


def test_online_failure_is_a_warning():
    class Broken:
        def search(self, *a):
            raise OSError("offline")

    rec = reconcile([], [R("x", "y", scheme="cat")], online=Broken())
    assert "online search failed" in rec.targets[0].target.extra["warnings"][0]


def test_write_outputs_and_reports(tmp_path):
    rec = reconcile(*_demo())
    paths = rec.write(tmp_path)
    lines = [json.loads(x) for x in paths["matches"].read_text("utf-8").splitlines()]
    assert lines and {"left_id", "right_scheme", "method", "confidence", "evidence"} <= set(lines[0])
    status = paths["status"].read_text("utf-8").splitlines()
    assert status[0].startswith("target\ttitle") and len(status) == 11
    assert "decision" in paths["review"].read_text("utf-8").splitlines()[0]
    cw = [json.loads(x) for x in paths["crosswalk"].read_text("utf-8").splitlines()]
    tawq = next(c for c in cw if "openiti:0456IbnHazm.TawqHamama.Shamela0010518-ara1" in c["ext_ids"])
    assert tawq["cluster_id"].startswith("w_") and tawq["openiti_uri"] == "0456IbnHazm.TawqHamama"
    md, ht = write_reports(rec, tmp_path, "t")
    assert "| Have | موجود | 4 |" in md.read_text("utf-8")
    h = ht.read_text("utf-8")
    assert h.startswith("<!doctype html>") and "prefers-color-scheme" in h and "AAlexandrina-164114" in h
    assert to_markdown(rec).count("## ") >= 6 and "<script" not in to_html(rec)


def test_outputs_follow_the_json_schemas(tmp_path):
    schema = resources.files("turath_match") / "schema"
    m = json.loads((schema / "match.schema.json").read_text("utf-8"))
    c = json.loads((schema / "crosswalk.schema.json").read_text("utf-8"))
    rec = reconcile(*_demo())
    paths = rec.write(tmp_path)

    def check(obj, sch):  # the subset of JSON Schema these files use: required keys and enums
        for k in sch.get("required", []):
            assert k in obj, k
        for k, spec in sch.get("properties", {}).items():
            if k in obj and "enum" in spec:
                assert obj[k] in spec["enum"], (k, obj[k])

    for line in paths["matches"].read_text("utf-8").splitlines():
        check(json.loads(line), m)
    for line in paths["crosswalk"].read_text("utf-8").splitlines():
        d = json.loads(line)
        check(d, c)
        assert d["cluster_id"].startswith("w_") and len(d["cluster_id"]) == 12


def test_a_cluster_is_named_after_its_plainest_full_title():
    from turath_match.reconcile import build_clusters
    from turath_match.work import match_work

    plain = Record("openiti", "a", "رسالة الغفران", "أبو العلاء المعري", death=449)
    noted = Record(
        "openiti",
        "b",
        "رسالة الغفران موافقا للمطبوع = رسالة الغفران - العلمية",
        "أبو العلاء المعري",
        death=449,
    )
    full = Record("openiti", "c", "التمهيد لما في الموطأ من المعاني والأسانيد", "ابن عبد البر", death=463)
    short = Record("openiti", "d", "التمهيد لما في الموطأ", "ابن عبد البر", death=463)
    recs = {r.key: r for r in (plain, noted, full, short)}
    clusters = build_clusters(recs, [match_work(plain, noted), match_work(full, short)])
    assert sorted(c["title_ar"] for c in clusters) == [full.title, plain.title]
