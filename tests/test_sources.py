import json
import sqlite3

import pytest

from turath_match.models import Record
from turath_match.sources import (
    ArchiveDump,
    ArchiveOrg,
    CsvSource,
    FolderSource,
    JsonlSource,
    OpenITI,
    ShamelaLocal,
    Waqfeya,
    WaqfeyaDump,
    open_source,
    parse_name,
    save_jsonl,
    schemes,
)
from turath_match.sources.archive import parse_files_xml
from turath_match.sources.openiti import parse_ed_info, repo_of, text_url
from turath_match.sources.shamela import find_master_db, load_cards, parse_card
from turath_match.sources.waqfeya import parse_detail, to_record

from .conftest import FIX


def test_csv_arabic_headers_and_sizes(tmp_path):
    p = tmp_path / "lib.csv"
    p.write_text(
        "العنوان,المؤلف,المحقق,الحجم,الملف\nالأم,الشافعي,رفعت فوزي,100;200,a.pdf;b.pdf\n,,,,\n", "utf-8"
    )
    (r,) = list(CsvSource(p).records())
    assert r.title == "الأم" and r.editor == "رفعت فوزي"
    assert [f.size for f in r.files] == [100, 200] and r.files[1].name == "b.pdf"


def test_csv_tsv_and_death_from_author(tmp_path):
    p = tmp_path / "w.tsv"
    p.write_text("title\tauthor\tvolumes\nالمغني\tابن قدامة ت 620 هـ\t١٥ مجلدا\n", "utf-8")
    (r,) = list(CsvSource(p).records())
    assert r.death == 620 and r.volumes == 15


def test_csv_without_title_column(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("name_of_thing\nx\n", "utf-8")
    p.write_text("foo,bar\n1,2\n", "utf-8")
    with pytest.raises(ValueError):
        list(CsvSource(p).records())


@pytest.mark.parametrize(
    "stem,want",
    [
        (
            "آداب الفتوى - النووي - ت بسام الجابي - دار الفكر دمشق",
            {
                "title": "آداب الفتوى",
                "author": "النووي",
                "editor": "بسام الجابي",
                "publisher": "دار الفكر دمشق",
            },
        ),
        ("الرسالة - الشافعي - ط الحلبي", {"title": "الرسالة", "author": "الشافعي", "publisher": "الحلبي"}),
        ("The Muqaddimah - Ibn Khaldun", {"title": "The Muqaddimah", "author": "Ibn Khaldun"}),
        ("كليلة_ودمنة", {"title": "كليلة ودمنة"}),
        ("الأم - الشافعي - 1321", {"title": "الأم", "author": "الشافعي", "year": "1321"}),
    ],
)
def test_parse_name_smart(stem, want):
    assert parse_name(stem) == want


def test_parse_name_profiles():
    assert parse_name("a - b", "title") == {"title": "a - b"}
    assert parse_name("Ibn Khaldun - Muqaddimah", "pattern:{author} - {title}") == {
        "author": "Ibn Khaldun",
        "title": "Muqaddimah",
    }
    assert parse_name("x - y - ت z - Brill", "warraq")["publisher"] == "Brill"


def test_folder_scan_groups_volumes(tmp_path):
    sec = tmp_path / "الحديث"
    vols = sec / "فتح الباري - ابن حجر"
    vols.mkdir(parents=True)
    for i in (1, 2, 3):
        (vols / f"{i:02d} - فتح الباري.pdf").write_bytes(b"%PDF" + b"0" * i)
    (sec / "الأربعون النووية - النووي.pdf").write_bytes(b"%PDF1")
    (sec / "notes.txt").write_text("not a book")
    recs = {r.title: r for r in FolderSource(tmp_path).records()}
    assert set(recs) == {"فتح الباري", "الأربعون النووية"}
    assert recs["فتح الباري"].volumes == 3 and len(recs["فتح الباري"].files) == 3
    assert recs["الأربعون النووية"].author == "النووي"
    with pytest.raises(ValueError):
        FolderSource(tmp_path / "nope")


def test_jsonl_roundtrip(tmp_path):
    r = Record("library", "1", "الأم", "الشافعي", death=204, flags={"thesis"})
    save_jsonl([r], tmp_path / "x.jsonl")
    (back,) = list(JsonlSource(tmp_path / "x.jsonl").records())
    assert back.to_dict() == r.to_dict()


def test_open_source_guesses(tmp_path):
    (tmp_path / "a.csv").write_text("title\nx\n", "utf-8")
    assert isinstance(open_source(str(tmp_path / "a.csv")), CsvSource)
    assert isinstance(open_source(str(tmp_path)), FolderSource)
    assert isinstance(open_source(f"archive:{FIX / 'x.jsonl'}"), ArchiveDump)
    with pytest.raises(ValueError):
        open_source(str(tmp_path / "file.bin"))
    assert "openiti" in schemes() and "shamela" in schemes()


def test_archive_files_xml():
    fs = parse_files_xml((FIX / "archive_files.xml").read_bytes(), "demo item")
    assert [f.name for f in fs] == ["kitab-01.pdf", "kitab-02.pdf"]
    assert fs[0].size == 12196642 and fs[0].md5.startswith("0f1e") and fs[0].sha1
    assert fs[0].url == "https://archive.org/download/demo%20item/kitab-01.pdf"


def test_archive_search_filters_and_caches(fake_http):
    http, t = fake_http({"advancedsearch": "archive_search.json", "_files.xml": "archive_files.xml"})
    recs = ArchiveOrg(http).search("كليلة ودمنة", "ابن المقفع")
    assert [r.id for r in recs] == ["demo-kalila-1922", "demo-kalila-study"]
    assert recs[0].files[0].size == 12196642
    n = len(t.calls)
    ArchiveOrg(http).search("كليلة ودمنة", "ابن المقفع")
    assert len(t.calls) == n  # all cached
    assert all("turath-match/" in h["User-Agent"] for _, h in t.calls)


def test_archive_dark_item(fake_http):
    import urllib.error

    err = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    http, _ = fake_http({"_files.xml": err})
    assert ArchiveOrg(http).files("dark") == []


def test_archive_dump(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text(
        json.dumps(
            {
                "id": "x",
                "title": ["a", "b"],
                "files": [
                    {"name": "v.pdf", "size": 5},
                    {"name": "v_text.pdf", "size": 3},
                    {"name": "t.jpg", "size": 1},
                ],
            }
        )
        + "\n"
        + json.dumps({"id": "y", "error": True})
        + "\n",
        "utf-8",
    )
    (r,) = list(ArchiveDump(p).records())
    assert r.title == "a ؛ b" and [f.name for f in r.files] == ["v.pdf"]


def test_waqfeya_pages_and_detail(fake_http):
    http, _ = fake_http(
        {
            "page=1&": "waqfeya_page1.json",
            "page=2&": "waqfeya_page2.json",
            "/books/tawq-1": "waqfeya_book.html",
        }
    )
    wq = Waqfeya(http, page_size=2)
    raws = list(wq.fetch_catalog())
    assert len(raws) == 3
    d = wq.fetch_detail(raws[0])
    r = to_record(d)
    assert (
        r.editor == "إحسان عباس" and r.publisher == "المؤسسة العربية للدراسات والنشر" and r.place == "بيروت"
    )
    assert r.volumes == 1 and r.files[0].name == "tawq.pdf" and r.extra["archive_items"] == ["demo-tawq"]
    assert parse_detail("<html></html>", "nope") is None


def test_waqfeya_dump_merges(tmp_path):
    p = tmp_path / "w.jsonl"
    p.write_text(
        json.dumps({"_id": "1", "name": "الأم", "permalink": "p", "author": {"name": "الشافعي"}})
        + "\n"
        + json.dumps({"_id": "1", "researcher": "رفعت"})
        + "\n"
        + json.dumps({"_id": "2", "error": 1})
        + "\n",
        "utf-8",
    )
    (r,) = list(WaqfeyaDump(p).records())
    assert r.editor == "رفعت" and r.url.endswith("/books/p")


def test_openiti_records():
    recs = list(OpenITI(FIX.parent.parent / "src/turath_match/demo/openiti.tsv").records())
    bukhari = [r for r in recs if r.work_uri == "0256Bukhari.Sahih"]
    assert len(bukhari) == 3 and all(r.death == 256 for r in bukhari)
    sh = next(r for r in bukhari if "Shamela" in r.id)
    assert sh.extra["source_collection"] == "Shamela" and sh.extra["source_id"] == "0001681"
    assert sh.url.startswith(
        "https://github.com/OpenITI/0275AH/blob/master/data/0256Bukhari/0256Bukhari.Sahih/"
    )
    assert "=" in next(r for r in bukhari if "JK" in r.id).title
    assert len(
        list(OpenITI(FIX.parent.parent / "src/turath_match/demo/openiti.tsv", primary_only=True).records())
    ) < len(recs)


def test_openiti_helpers():
    assert repo_of("0256") == "0275AH" and repo_of("0275") == "0275AH" and repo_of("0276") == "0300AH"
    assert text_url("v", "0001X.Y", "") == ""
    e = parse_ed_info("القاهرة :: السابعة :: 1418ه، 1988م :: مكتبة الخانجي")
    assert e == {
        "place": "القاهرة",
        "edition": "السابعة",
        "year": "1418ه، 1988م",
        "publisher": "مكتبة الخانجي",
    }
    assert parse_ed_info("تحقيق وشرح : أحمد محمد شاكر") == {"editor": "أحمد محمد شاكر"}


def _shamela(tmp_path):
    db = tmp_path / "shamela" / "database" / "master.db"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.executescript("""
    CREATE TABLE category (category_id INTEGER PRIMARY KEY, category_name TEXT, category_order INTEGER);
    CREATE TABLE author (author_id INTEGER PRIMARY KEY, author_name TEXT, death_number INTEGER, death_text TEXT, alpha INTEGER);
    CREATE TABLE book (book_id INTEGER PRIMARY KEY, book_name TEXT, book_category INTEGER, book_type INTEGER,
      book_date INTEGER, authors TEXT, main_author INTEGER, printed INTEGER, group_id INTEGER, hidden INTEGER,
      major_online INTEGER, minor_online INTEGER, major_ondisk INTEGER, minor_ondisk INTEGER, pdf_links TEXT,
      pdf_ondisk INTEGER, pdf_online INTEGER, cover_ondisk INTEGER, cover_online INTEGER, meta_data TEXT,
      parent INTEGER, alpha INTEGER, group_order INTEGER, book_up INTEGER);
    INSERT INTO category VALUES (1, 'أصول الفقه', 1);
    INSERT INTO author VALUES (10, 'الشافعي', 204, '204', 1), (11, 'مؤلف مجهول', 99999, '', 1);
    INSERT INTO book (book_id, book_name, book_category, main_author, printed, pdf_links, hidden)
      VALUES (100, 'الرسالة', 1, 10, 1, '{"files": ["/risala/r.pdf"], "size": 4410337}', 0),
             (101, 'مخطوط في الأصول - مخطوط', 1, 11, 3, NULL, 0),
             (102, 'مخفي', 1, 10, 1, NULL, 1);
    """)
    c.commit()
    c.close()
    return tmp_path / "shamela"


def test_shamela_reader(tmp_path):
    home = _shamela(tmp_path)
    cards = tmp_path / "cards.jsonl"
    cards.write_text(
        json.dumps(
            {
                "id": "100",
                "body_store": "الكتاب: الرسالة\rالمحقق: أحمد شاكر\rالناشر: مكتبة الحلبي، مصر"
                "\rالطبعة: الأولى، 1358هـ\rعدد الأجزاء: ١\rويليه: جماع العلم",
            },
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )
    recs = {r.id: r for r in ShamelaLocal(home, cards).records()}
    assert set(recs) == {"100", "101"}
    r = recs["100"]
    assert r.author == "الشافعي" and r.death == 204 and r.editor == "أحمد شاكر" and r.volumes == 1
    assert r.files[0].size == 4410337 and r.url == "https://shamela.ws/book/100"
    assert recs["101"].death is None and "manuscript" in recs["101"].flags
    assert find_master_db(home) == home / "database" / "master.db"
    assert len(list(open_source(f"shamela:{home}").records())) == 2
    assert load_cards(cards)["100"]["joined"] == ["ويليه: جماع العلم"]


def test_shamela_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_master_db(tmp_path)


def test_parse_card_fields():
    d = parse_card("المؤلف: النووي\nتحقيق: بسام\nالمحقق: آخر\nعدد الأجزاء: 4\nسطر بلا حقل")
    assert d["editor"] == "بسام ؛ آخر" and d["volumes_n"] == 4
