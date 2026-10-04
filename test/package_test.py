# What the published dataset says, built from a crawled month by package.py.
#
#   uv run --no-project --with pytest pytest -p no:cacheprovider test/package_test.py
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("package", Path(__file__).parent.parent / "package.py")
pk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pk)


def pair(en, text, office="delhi-en", lang="hi", en_prid="1", text_prid="2"):
    return {"lang": lang, "en": en, "text": text, "sim": 0.9, "numbers": None, "confidence": "normal",
            "prid": en_prid, "en_prid": en_prid, "text_prid": text_prid, "date": "28 NOV 2025 6:07PM by PIB Delhi", "office": office}


def test_a_repeated_pair_is_one_row_with_its_count():
    rows = pk.fold([pair("Friends,", "मित्रों,"), pair("Friends,", "मित्रों,", en_prid="5", text_prid="6"), pair("Thank you.", "धन्यवाद।")], {})
    assert [(r["en"], r["occurrences"], r["en_prid"]) for r in rows] == [("Friends,", 2, "1"), ("Thank you.", 1, "1")]


def test_the_copy_flag_is_known_only_where_a_sample_was_checked():
    flags = {("hi", "Friends,", "मित्रों,"): True}
    rows = pk.fold([pair("Friends,", "मित्रों,"), pair("Thank you.", "धन्यवाद।")], flags)
    assert [r["google_copy"] for r in rows] == [True, None]


def test_the_row_names_its_fields_for_a_reader():
    row = pk.fold([pair("Friends,", "मित्रों,")], {})[0]
    assert set(row) == {"lang", "en", "text", "similarity", "numbers_agree", "confidence", "google_copy", "occurrences",
                        "en_prid", "text_prid", "office", "date", "posted_by"}
    assert (row["date"], row["posted_by"]) == ("2025-11-28", "PIB Delhi")


def test_a_document_pair_found_from_both_sides_is_one_row():
    delhi = {"prid": "10", "date": "D", "ministry": "M", "byLang": {
        "en": {"prid": "10", "title": "T", "body": "One."}, "mr": {"prid": "20", "title": "शी", "body": "एक."}}}
    mumbai = {"prid": "20", "date": "D", "ministry": "M", "byLang": {
        "mr": {"prid": "20", "title": "शी", "body": "एक."}, "en": {"prid": "10", "title": "T", "body": "One."}}}
    docs = pk.documents([("delhi-en", delhi), ("mumbai-mr", mumbai)])
    assert [(d["lang"], d["en_prid"], d["text_prid"], d["office"]) for d in docs] == [("mr", "10", "20", "delhi-en")]


def test_a_date_pib_wrote_is_read_and_one_it_did_not_is_empty():
    assert pk.posted("05 NOV 2018 2:20PM by PIB Bengaluru") == ("2018-11-05", "PIB Bengaluru")
    assert pk.posted("") == ("", "")


def test_a_pair_is_kept_only_when_each_side_is_in_its_own_script():
    # 3.5% of the November 2025 pairs were links, hashtags, staff initials or lines
    # left in English on a translated page; they align easily because they match themselves.
    keep = pair("The President inaugurated it.", "राष्ट्रपति ने इसका उद्घाटन किया।")
    link = pair("Visitors https://visit.rashtrapatibhavan.gov.in/plan-visit", "आगंतुक https://visit.rashtrapatibhavan.gov.in/plan-visit")
    english = pair("For more information, click on:", "For more information, click on:", lang="gom")
    initials = pair("SC/AK/DS/DM", "SC/AK/DS/DM", lang="as")
    quoted = pair("जय जय सियाराम।", "জয় জয় সিয়ারাম।", lang="mni")
    khasi = pair("The Prime Minister spoke.", "U Prime Minister u la kren.", lang="kha")
    rows = pk.fold([keep, link, english, initials, quoted, khasi], {})
    assert [r["text"] for r in rows] == ["राष्ट्रपति ने इसका उद्घाटन किया।", "U Prime Minister u la kren."]
