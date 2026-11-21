import pytest

from turath_match.titles import analyse, base, compare_titles, has, tok


def cmp(a, b, names=()):
    return compare_titles(analyse(a), analyse(b), names)


def test_tok_forms():
    assert tok("ابن") == "بن"
    assert tok("الديوان") == tok("ديوان") == "شعر"
    assert tok("الله") == "الله"
    assert tok("والنهاية") == "نهايه" or tok("والنهاية") == "نهاية"


def test_base_strips_joined_particles():
    assert base("بشرح") == "شرح"
    assert base("ومختصر") == "مختصر"
    assert base("بيان") == "بيان"


def test_has_tolerates_particles():
    assert has("علم", {"بعلم"})
    assert has("وكتابه", {"كتابه"})
    assert not has("علم", {"عالم"})


def test_edition_tails_become_hints():
    info = analyse("فتح الباري بشرح صحيح البخاري - ت محب الدين الخطيب - ط السلفية")
    assert info.editor_hint == "محب الدين الخطيب"
    assert info.publisher_hint == "السلفية"
    assert " ".join(info.forms[0].words).startswith("فتح")


def test_alternative_titles_and_joined_works():
    info = analyse("الجامع الصحيح = صحيح البخاري")
    assert len(info.forms) == 2
    info = analyse("طبقات الصوفية ويليه ذكر النسوة المتعبدات")
    assert info.joined == ["ذكر النسوة المتعبدات"]
    assert "نسوه" not in info.forms[0].words and "نسوة" not in info.forms[0].words


def test_flags():
    assert "thesis" in analyse("منهج ابن حجر - رسالة ماجستير").flags
    assert "manuscript" in analyse("مزيد فتح الباري - مخطوط").flags
    assert "part" in analyse("تاريخ بغداد الجزء 3").flags


def test_attribution_stripped_with_author():
    info = analyse("شعب الإيمان للبيهقي", "أبو بكر البيهقي")
    assert info.attribution == {"البيهقي"}
    assert len(info.forms[0].core) == 2


@pytest.mark.parametrize(
    "a,b,kind",
    [
        ("صحيح البخاري", "صحيح البخاري", "exact"),
        ("كتاب الأم", "الأم", "exact"),
        ("فتح الباري", "فتح الباري بشرح صحيح البخاري", "head"),
        ("شرح صحيح مسلم", "صحيح مسلم", "related"),
        ("مختصر تفسير ابن كثير", "تفسير ابن كثير", "related"),
        ("ذيل تاريخ بغداد", "تاريخ بغداد", "related"),
        ("السنن الكبرى", "السنن الصغرى", "conflict"),
        ("الموطأ - رواية يحيى الليثي", "الموطأ - رواية أبي مصعب", "conflict"),
        ("سنن أبي داود", "سنن النسائي", "none"),
        ("البداية والنهاية في التاريخ", "البداية والنهاية في الأخبار", "fuzzy"),
    ],
)
def test_compare_kinds(a, b, kind):
    assert cmp(a, b).kind == kind


def test_related_direction():
    c = cmp("صحيح مسلم", "شرح صحيح مسلم")
    assert c.relation == "commentary" and c.derived_side == "right"
    c = cmp("فتح الباري بشرح صحيح البخاري", "صحيح البخاري")
    assert c.relation == "commentary" and c.derived_side == "left"


def test_part_on_one_side_is_related_part():
    c = cmp("الطبقات الكبرى - السفر الثاني", "الطبقات الكبرى")
    assert c.kind == "related" and c.relation == "part" and c.derived_side == "left"


def test_size_word_on_one_side_caps_score():
    c = cmp("المدونة الكبرى", "المدونة")
    assert c.kind == "head" and c.score <= 0.7


def test_author_names_in_title_do_not_separate():
    assert cmp("مقدمة ابن خلدون", "المقدمة", names={"خلدون"}).kind == "exact"
    assert cmp("مقدمة ابن خلدون", "المقدمة").kind == "head"


def test_edition_written_without_a_dash():
    # «ت» and «ط» are not Arabic words: at the end of a title they open the editor or the publisher
    info = analyse("البعث والنشور للبيهقي ت الشوامي = البعث والنشور", "أبو بكر البيهقي")
    assert info.editor_hint == "الشوامي" and [f.core for f in info.forms] == [["بعث", "نشور"]] * 2
    info = analyse("التبيان في أيمان القرآن ط عالم الفوائد")
    assert info.publisher_hint == "عالم الفوائد" and info.forms[0].core == ["تبيان", "ايمان", "قران"]
    # with the dash, as before; the colon after «ت» is the same mark
    info = analyse(
        "القواعد والفوائد الأصولية - ت: الفقي = القواعد والفوائد الأصولية وما يتعلق بها من الأحكام"
    )
    assert info.editor_hint == "الفقي" and info.forms[0].core == ["قواعد", "فوايد", "اصوليه"]
    assert analyse("الطب النبوي").forms[0].core == ["طب", "نبوي"]  # a word that holds «ط» is left alone


def test_publisher_after_the_dash_is_not_the_title():
    info = analyse("تفسير النسفي - دار النفائس")
    assert info.publisher_hint == "دار النفائس" and info.forms[0].words == ["تفسير", "نسفي"]
    # the alternative title after an imprint still counts, and a recension after the dash is still the title
    info = analyse("جزء ابن عيينة - مكتبة المنار = جزء فيه حديث سفيان بن عيينة")
    assert info.publisher_hint == "مكتبة المنار" and len(info.forms) == 2
    info = analyse("موطأ مالك - رواية أبي مصعب = الموطأ")
    assert "روايه" in info.forms[0].words and info.forms[1].words == ["موطا"]


@pytest.mark.parametrize(
    "noted",
    [
        "تفسير البحر المحيط موافق للمطبوع",
        "تفسير البحر المحيط موافقا للمطبوع داخل الصفحات",
        "تفسير البحر المحيط مشكول",
        "تفسير البحر المحيط - نسخة أخرى مشكولة",
        "تفسير البحر المحيط محققا",
    ],
)
def test_notes_about_the_copy_are_not_the_title(noted):
    assert cmp(noted, "تفسير البحر المحيط").kind == "exact"
    assert analyse("مشكل الآثار").forms[0].core == ["مشكل", "اثار"]  # «مشكل» is a title word


def test_a_note_is_not_an_alternative_title():
    # «… = مقابل» («collated») is written on many books of one author: it names none of them
    a = analyse("الأهوال لابن أبي الدنيا - ط أطلس الخضراء = مقابل = الأهوال", "ابن أبي الدنيا")
    b = analyse("الورع = الورع لابن أبي الدنيا - ط أطلس الخضراء = مقابل", "ابن أبي الدنيا")
    assert [f.core for f in a.forms] == [["اهوال"], ["اهوال"]]
    assert compare_titles(a, b).kind == "none"
    assert analyse("المحقق").forms[0].words == ["محقق"]  # all the title there is: kept
