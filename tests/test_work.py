import pytest

from turath_match import match_work
from turath_match.models import DIFFERENT, MATCH, RELATED, REVIEW, SAME, UNCERTAIN

from .conftest import R


def test_same_work_alt_title():
    m = match_work(R("صحيح البخاري", "البخاري"), R("الجامع الصحيح = صحيح البخاري", "محمد بن إسماعيل البخاري"))
    assert m.verdict == SAME and m.status == MATCH and m.method == "exact_title_author"
    assert any(e.kind == "author" and e.weight > 0 for e in m.evidence)


def test_same_title_other_author_is_another_work():
    m = match_work(R("الزهد", "أحمد بن حنبل"), R("الزهد", "عبد الله بن المبارك"))
    assert m.verdict == DIFFERENT


def test_commentary_is_not_the_work():
    m = match_work(R("فتح الباري بشرح صحيح البخاري", "ابن حجر"), R("صحيح البخاري", "البخاري"))
    assert m.verdict == RELATED and m.relation == "commentary" and m.status != MATCH


def test_abridgement_by_another_author():
    m = match_work(R("مختصر صحيح مسلم", "المنذري"), R("صحيح مسلم", "مسلم بن الحجاج"))
    assert m.verdict == RELATED and m.relation == "abridgement"


def test_other_recension():
    m = match_work(
        R("الموطأ - رواية يحيى بن يحيى", "مالك بن أنس"), R("الموطأ - رواية أبي مصعب", "مالك بن أنس")
    )
    assert m.verdict == RELATED and m.relation == "recension"


def test_common_name_alone_never_proves():
    m = match_work(R("الرسالة", "محمد"), R("الرسالة", "محمد بن إدريس الشافعي"))
    assert m.verdict == UNCERTAIN and m.status == REVIEW


def test_missing_author_goes_to_review():
    m = match_work(R("كليلة ودمنة"), R("كليلة ودمنة", "ابن المقفع"))
    assert m.verdict == UNCERTAIN and m.status == REVIEW


def test_title_attribution_counts_as_author():
    m = match_work(R("شعب الإيمان للبيهقي"), R("شعب الإيمان", "أبو بكر البيهقي"))
    assert m.verdict == SAME


def test_death_year_conflict():
    m = match_work(R("الأمالي", "ابن الشجري", death=542), R("الأمالي", "ابن الشجري", death=600))
    assert m.verdict == DIFFERENT
    assert any("death" in e.detail for e in m.evidence)


def test_death_year_agreement_is_evidence():
    m = match_work(R("الأمالي", "ابن الشجري", death=542), R("أمالي ابن الشجري", "ابن الشجري", death=542))
    assert m.verdict == SAME
    assert any(e.kind == "death" for e in m.evidence)


def test_work_uri_decides():
    a = R("الكامل", "المبرد", work_uri="0285Mubarrad.Kamil")
    b = R("الكامل في اللغة", "المبرد", work_uri="0285Mubarrad.Kamil")
    assert match_work(a, b).score >= 0.99


def test_subtitle_same_author_matches():
    m = match_work(R("فتح الباري", "ابن حجر"), R("فتح الباري بشرح صحيح البخاري", "ابن حجر العسقلاني"))
    assert m.verdict == SAME and m.status == MATCH and m.method == "fuzzy_title_author"


@pytest.mark.parametrize("t1,t2", [("سنن أبي داود", "سنن النسائي"), ("تاريخ دمشق", "تاريخ بغداد")])
def test_different_titles(t1, t2):
    assert match_work(R(t1, "x y"), R(t2, "x y")).verdict == DIFFERENT


def test_explain_lists_every_reason():
    text = match_work(R("الزهد", "أحمد بن حنبل"), R("الزهد", "عبد الله بن المبارك")).explain()
    assert text.startswith("work: different")
    assert "title" in text and "author" in text


def test_to_dict_schema_fields():
    d = match_work(R("صحيح البخاري", "البخاري"), R("صحيح البخاري", "البخاري")).to_dict()
    for k in (
        "left_scheme",
        "left_id",
        "right_scheme",
        "right_id",
        "level",
        "verdict",
        "method",
        "score",
        "confidence",
        "status",
        "evidence",
    ):
        assert k in d
    assert d["confidence"] == "high"


def test_common_name_with_same_death_year():
    m = match_work(R("الأم", "الشافعي", death=204), R("الأم", "محمد بن إدريس الشافعي", death=204))
    assert m.verdict == SAME
    assert match_work(R("الأم", "الشافعي"), R("الأم", "محمد بن إدريس الشافعي")).verdict == UNCERTAIN


def test_work_id_recipe_is_stable():
    from turath_match.text import work_id

    assert work_id("كتاب الأمّ (ط بولاق)", "الإمام الشافعي؛ ت 204") == work_id("الام", "الشافعي")
    assert work_id("الأم", "الشافعي").startswith("w_") and len(work_id("x", "")) == 12
    import hashlib

    assert (
        work_id("صحيح البخاري", "البخاري")
        == "w_" + hashlib.sha1("صحيح البخاري|البخاري".encode()).hexdigest()[:10]
    )


def test_almusamma_is_an_alternative_title():
    m = match_work(
        R("تفسير القشيري المسمى لطائف الإشارات", "القشيري"), R("لطائف الإشارات", "عبد الكريم القشيري")
    )
    assert m.verdict == SAME and m.status == MATCH


def test_fuller_title_holding_every_word():
    m = match_work(
        R("كشف المخدرات والرياض المزهرات لشرح أخصر المختصرات", "البعلي"),
        R("كشف المخدرات لشرح أخصر المختصرات", "عبد الرحمن بن عبد الله البعلي"),
    )
    assert m.verdict == SAME


def test_leading_masala_and_juz_fihi():
    assert (
        match_work(
            R("مسألة الاحتجاج بالشافعي", "الخطيب البغدادي"), R("الاحتجاج بالشافعي", "الخطيب البغدادي")
        ).verdict
        == SAME
    )
    assert match_work(R("جزء فيه حديث لوين", "لوين"), R("حديث لوين", "لوين")).verdict == SAME


def test_collection_title_never_matches_alone():
    m = match_work(R("رسائل الجاحظ", "الجاحظ"), R("رسائل الجاحظ", "الجاحظ"))
    assert m.verdict == UNCERTAIN and m.status == REVIEW
    assert match_work(R("الرسائل الأدبية", "الجاحظ"), R("الرسائل الأدبية", "الجاحظ")).status == REVIEW


def test_death_slack_with_full_names():
    m = match_work(
        R("الإماء الشواعر", "أبو الفرج الأصبهاني", death=356),
        R("الإماء الشواعر", "أبو الفرج الأصبهاني", death=362),
    )
    assert m.verdict == SAME and m.status == REVIEW
    assert any(e.kind == "death" and e.weight < 0 for e in m.evidence)


def test_death_note_inside_the_name():
    m = match_work(R("نور اليقين", "محمد الخضري (المتوفى: 1345هـ)"), R("نور اليقين", "محمد الخضري ت 1345"))
    assert m.verdict == SAME


def test_long_title_tolerates_one_word_in_four():
    a = R("القواعد والفوائد الأصولية ومايتبعها من الأحكام الفرعية", "ابن اللحام")
    b = R("القواعد والفوائد الأصولية وما يتبعها من الأحكام الفرعية", "ابن اللحام")
    assert match_work(a, b).verdict == SAME
