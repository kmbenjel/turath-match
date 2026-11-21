"""The built-in fallback (used when arabic-bib is not importable) keeps the same contract."""

import pytest

from turath_match import text


@pytest.fixture
def fallback(monkeypatch):
    monkeypatch.setattr(text, "_HAS_AB", False)
    return text


def test_keys(fallback):
    assert fallback.search_key("إحياءُ علوم الدّين ١٢") == "احيا علوم الدين 12"
    assert fallback.title_key("كتاب الأمّ (ط بولاق) - ت فلان") == "الام"
    assert "الشافعي" in fallback.author_tokens("الإمام محمد بن إدريس الشافعي")
    assert fallback.author_key("ابن حجر العسقلاني") == "العسقلاني حجر"


@pytest.mark.parametrize(
    "s,y",
    [
        ("ابن تيمية ت 728 هـ", 728),
        ("(المتوفى: ٧٢٨هـ)", 728),
        ("661-728", 728),
        ("728", 728),
        ("", None),
        ("بلا تاريخ", None),
    ],
)
def test_parse_death(fallback, s, y):
    assert fallback.parse_death(s) == y


def test_match_authors(fallback):
    assert fallback.match_authors("ابن حجر", "أحمد بن علي بن حجر العسقلاني").verdict == "same"
    assert fallback.match_authors("محمد", "محمد بن إدريس الشافعي").verdict == "unknown"
    assert fallback.match_authors("النووي", "الذهبي").verdict == "different"
    assert fallback.match_authors("", "الذهبي").verdict == "unknown"
    assert fallback.match_authors("الذهبي ت 748", "الذهبي ت 700").verdict == "different"
    assert fallback.match_authors("ابن المقفع، عبد الله", "عبد الله بن المقفع").verdict == "same"
    assert fallback.match_authors("الطوسي", "الطوسي", common=["الطوسي"]).verdict in ("same", "unknown")


def test_people_and_publishers(fallback):
    assert fallback.same_person("أحمد شاكر", "أحمد محمد شاكر") is True
    assert fallback.same_person("", "x") is None
    assert fallback.same_publisher("المكتبة السلفية", "السلفية") is True
    assert fallback.same_publisher("دار الفكر", "دار الفكر العربي") is False
    assert fallback.same_publisher("", "دار الفكر") is None
    assert fallback.same_publisher("دار", "مكتبة") is False


def test_uninvert():
    assert text.uninvert('"إبن المقفع، عبد الله"') == "عبد الله ابن المقفع"
    assert text.uninvert("الجاحظ، عمرو بن بحر، 255 هـ") == "عمرو بن بحر الجاحظ 255 هـ"
    assert text.uninvert("صحيح البخاري") == "صحيح البخاري"


def test_death_year_in_either_calendar():
    from turath_match import Record, match_work
    from turath_match.text import parse_death

    assert parse_death("محمود شاكر (ت 1997 م)") == 1417
    assert parse_death("محمود شاكر (ت 1418 هـ)") == 1418
    assert parse_death("ولد سنة 1350 هـ") is None  # a birth year is not a death year
    a = Record("a", "1", "أباطيل وأسمار", "محمود محمد شاكر (ت 1997 م)")
    b = Record("b", "2", "أباطيل وأسمار", "محمود محمد شاكر (ت 1418 هـ)")
    m = match_work(a, b)
    assert m.verdict == "same" and any(e.kind == "death" and e.weight > 0 for e in m.evidence)
