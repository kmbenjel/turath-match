from turath_match import match_edition
from turath_match.models import DIFFERENT, EXACT_SIZE, HASH, SAME, UNCERTAIN, FileRef

from .conftest import R


def test_exact_size_proves_edition(files):
    a = R("x", files=files(12_000_000))
    b = R("x", files=files(5_000_000, 12_000_000))
    m = match_edition(a, b)
    assert m.verdict == SAME and m.method == EXACT_SIZE
    assert m.relation == "part"  # one of two volumes


def test_small_equal_sizes_prove_nothing(files):
    m = match_edition(R("x", files=files(2048)), R("x", files=files(2048)))
    assert m.verdict == UNCERTAIN


def test_hash_proves_edition():
    a = R("x", files=[FileRef("a.pdf", 10, md5="abc")])
    b = R("x", files=[FileRef("b.pdf", 11, md5="abc")])
    assert match_edition(a, b).method == HASH


def test_editor_and_publisher_agree():
    a = R("الرسالة", editor="أحمد محمد شاكر", publisher="مصطفى البابي الحلبي")
    b = R("الرسالة", editor="أحمد شاكر", publisher="مطبعة مصطفى البابي الحلبي")
    m = match_edition(a, b)
    assert m.verdict == SAME and m.score >= 0.85


def test_editor_differs():
    m = match_edition(R("x", editor="عائشة عبد الرحمن"), R("x", editor="كامل كيلاني"))
    assert m.verdict == DIFFERENT


def test_volumes_differ():
    m = match_edition(R("x", publisher="دار الفكر", volumes=4), R("x", publisher="دار الفكر", volumes=9))
    assert m.verdict == DIFFERENT


def test_thesis_is_not_the_printed_edition():
    m = match_edition(R("تحقيق كتاب الأموال - رسالة ماجستير"), R("كتاب الأموال", publisher="دار الفكر"))
    assert m.verdict == DIFFERENT


def test_hints_from_title_tails():
    m = match_edition(
        R("فتح الباري - ت محب الدين الخطيب - ط السلفية"),
        R("فتح الباري", editor="محب الدين الخطيب", publisher="المكتبة السلفية"),
    )
    assert m.verdict == SAME


def test_nothing_known():
    m = match_edition(R("x"), R("x"))
    assert m.verdict == UNCERTAIN and m.evidence


def test_only_editor_given_and_agrees():
    m = match_edition(R("x", editor="إحسان عباس", publisher="المؤسسة العربية"), R("x", editor="إحسان عباس"))
    assert m.verdict == SAME and m.score >= 0.85


def test_year_disagreement_is_another_printing():
    m = match_edition(R("x", publisher="بولاق", year="1311"), R("x", publisher="بولاق", year="1325"))
    assert any(e.kind == "year" and e.weight < 0 for e in m.evidence)


def test_similar_publishers_are_not_one():
    m = match_edition(R("x", publisher="دار الفكر"), R("x", publisher="دار الفكر العربي"))
    assert m.verdict == DIFFERENT


def test_publisher_with_and_without_city():
    m = match_edition(
        R("x", editor="الحسين آيت سعيد", publisher="دار طيبة - الرياض"),
        R("x", editor="د الحسين آيت سعيد", publisher="دار طيبة، الرياض - السعودية"),
    )
    assert m.verdict == SAME


def test_note_in_editor_field_is_not_an_editor():
    m = match_edition(R("x", editor="مخطوط نشر في برنامج جوامع الكلم"), R("x", editor="نبيل جرار"))
    assert m.verdict != DIFFERENT


def test_two_agreeing_fields_without_editor():
    m = match_edition(
        R("x", publisher="مطبعة الصاوي", year="1355 هـ"), R("x", publisher="مطبعة الصاوي", year="١٣٥٥ هـ")
    )
    assert m.verdict == SAME and m.status == "match"
