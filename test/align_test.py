# The sentence splitter, number check, cache and alignment in align.py. No model is loaded.
#
#   uv run --no-project --with pytest --with numpy pytest -p no:cacheprovider test/align_test.py
import importlib.util
import sys
from pathlib import Path

# Loading the script must leave no bytecode beside it.
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("align", Path(__file__).parent.parent / "align.py")
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)


def test_english_titles_initials_and_lowercase_continuations_do_not_end_a_sentence():
    text = "Union Minister Dr. Mansukh Mandaviya inaugurated it. It is important. Shri P. K. Mishra and Rs. 500 crore etc. were present."
    assert pa.sentences(text) == [
        "Union Minister Dr. Mansukh Mandaviya inaugurated it.",
        "It is important.",
        "Shri P. K. Mishra and Rs. 500 crore etc. were present.",
    ]


def test_marathi_title_and_initial_hold_but_a_short_verb_still_ends_the_sentence():
    text = "केंद्रीय मंत्री डॉ. मनसुख मांडविया यांनी उद्घाटन केले. हे महत्त्वाचे आहे. एल. मुरुगन उपस्थित होते."
    assert pa.sentences(text) == [
        "केंद्रीय मंत्री डॉ. मनसुख मांडविया यांनी उद्घाटन केले.",
        "हे महत्त्वाचे आहे.",
        "एल. मुरुगन उपस्थित होते.",
    ]


def test_kannada():
    text = "ಕೇಂದ್ರ ಸಚಿವ ಡಾ. ಮನ್ಸುಖ್ ಮಾಂಡವೀಯ ಉದ್ಘಾಟಿಸಿದರು. ಇದು ಮುಖ್ಯ ಎಂದರು. ಎಲ್. ಮುರುಗನ್ ಹಾಜರಿದ್ದರು."
    assert pa.sentences(text) == ["ಕೇಂದ್ರ ಸಚಿವ ಡಾ. ಮನ್ಸುಖ್ ಮಾಂಡವೀಯ ಉದ್ಘಾಟಿಸಿದರು.", "ಇದು ಮುಖ್ಯ ಎಂದರು.", "ಎಲ್. ಮುರುಗನ್ ಹಾಜರಿದ್ದರು."]


def test_tamil():
    text = "மத்திய அமைச்சர் திரு. எல். முருகன் தொடங்கி வைத்தார். இது முக்கியம் ஆகும். ரூ. 500 கோடி ஒதுக்கப்பட்டது."
    assert pa.sentences(text) == ["மத்திய அமைச்சர் திரு. எல். முருகன் தொடங்கி வைத்தார்.", "இது முக்கியம் ஆகும்.", "ரூ. 500 கோடி ஒதுக்கப்பட்டது."]


def test_punjabi_ends_at_the_danda_and_keeps_its_title_and_initial():
    text = "ਕੇਂਦਰੀ ਮੰਤਰੀ ਡਾ. ਮਨਸੁਖ ਮਾਂਡਵੀਆ ਨੇ ਉਦਘਾਟਨ ਕੀਤਾ। ਇਹ ਅਹਿਮ ਹੈ। ਐੱਲ. ਮੁਰੂਗਨ ਮੌਜੂਦ ਸਨ।"
    assert pa.sentences(text) == ["ਕੇਂਦਰੀ ਮੰਤਰੀ ਡਾ. ਮਨਸੁਖ ਮਾਂਡਵੀਆ ਨੇ ਉਦਘਾਟਨ ਕੀਤਾ।", "ਇਹ ਅਹਿਮ ਹੈ।", "ਐੱਲ. ਮੁਰੂਗਨ ਮੌਜੂਦ ਸਨ।"]


def test_a_sentence_may_begin_with_a_number():
    text = "ಸಮ್ಮೇಳನ ಇಂದು ಮುಕ್ತಾಯಗೊಂಡಿತು. 2025ರ ನವೆಂಬರ್ 27ರಂದು ಆರಂಭವಾಗಿತ್ತು."
    assert pa.sentences(text) == ["ಸಮ್ಮೇಳನ ಇಂದು ಮುಕ್ತಾಯಗೊಂಡಿತು.", "2025ರ ನವೆಂಬರ್ 27ರಂದು ಆರಂಭವಾಗಿತ್ತು."]
    assert pa.sentences("It closed today. 2025 was a record year.") == ["It closed today.", "2025 was a record year."]


def test_a_dotted_abbreviation_does_not_end_a_sentence():
    assert pa.sentences("दूरी 5 कि.मी. है। आगे बढ़ें।") == ["दूरी 5 कि.मी. है।", "आगे बढ़ें।"]


def test_a_decimal_or_a_date_can_end_a_sentence():
    assert pa.sentences("Growth was (17.92%). Top states follow.") == ["Growth was (17.92%).", "Top states follow."]
    assert pa.sentences("It is dated 29.10.2025. This applies now.") == ["It is dated 29.10.2025.", "This applies now."]


def test_numbers_read_every_script_and_ignore_grouping_commas():
    assert pa.numbers("Rs 4,500 on 28 November 2025") == ["2025", "28", "4500"]
    assert pa.numbers("४,५०० रुपये, 28 नवंबर २०२५") == ["2025", "28", "4500"]
    assert pa.numbers("১,০০,০০০ টাকা") == ["100000"]
    assert pa.numbers("in 2024 2025 and 2026") == ["2024", "2025", "2026"]


def test_numbers_count_millions_and_lakhs_alike():
    # 6.3 million is 63 lakh; 4,500 crore is 45 billion. Seen in the pilot as false disagreements.
    assert pa.numbers("over 6.3 million Scouts") == pa.numbers("63 लाखांहून अधिक बालवीर") == ["6300000"]
    assert pa.numbers("Rs 45 billion") == pa.numbers("₹4,500 करोड़") == pa.numbers("4,500 கோடி") == ["45000000000"]
    assert pa.numbers("2.4 million girls") == pa.numbers("24 ಲಕ್ಷಕ್ಕೂ ಹೆಚ್ಚು") == ["2400000"]
    # Kannada's "ten lakh", and the English words written in the other scripts.
    assert pa.numbers("357 million tonnes") == pa.numbers("357 ದಶಲಕ್ಷ ಟನ್") == pa.numbers("357 मिलियन टन") == ["357000000"]
    assert pa.numbers("$5 billion") == pa.numbers("5 பில்லியன் டாலர்") == ["5000000000"]


def test_numbers_agree_only_says_something_when_a_side_has_numbers():
    assert pa.numbers_agree("Rs 4,500 crore in 2025", "२०२५ में ४,५०० करोड़") is True
    assert pa.numbers_agree("Rs 4,500 crore in 2025", "२०२४ में ४,५०० करोड़") is False
    assert pa.numbers_agree("It is important.", "यह महत्वपूर्ण है।") is None


# Alignment on fake vectors: each text's meaning is a direction, so the right
# match scores 1 and any other 0. No model is loaded.
import numpy as np

MEANINGS = ["A", "B", "C", "AB"]


def fake_vectors(meaning: dict[str, str]):
    """An encoder that maps each text to the unit vector of its meaning; unknown text to zero."""
    calls: list[list[str]] = []

    def encode(texts):
        calls.append(list(texts))
        out = np.zeros((len(texts), len(MEANINGS)), dtype=np.float32)
        for i, t in enumerate(texts):
            if t in meaning:
                out[i, MEANINGS.index(meaning[t])] = 1
        return out

    return encode, calls


def test_align_matches_one_to_one():
    encode, _ = fake_vectors({"One.": "A", "Two.": "B", "Three.": "C", "एक।": "A", "दो।": "B", "तीन।": "C"})
    vec = pa.embedder(encode)(pa.needed(["One.", "Two.", "Three."], ["एक।", "दो।", "तीन।"]))
    assert pa.align(vec, ["One.", "Two.", "Three."], ["एक।", "दो।", "तीन।"]) == [("One.", "एक।", 1.0), ("Two.", "दो।", 1.0), ("Three.", "तीन।", 1.0)]


def test_align_joins_two_sentences_translated_as_one():
    encode, _ = fake_vectors({"One.": "A", "Two.": "B", "One. Two.": "AB", "एक और दो।": "AB"})
    vec = pa.embedder(encode)(pa.needed(["One.", "Two."], ["एक और दो।"]))
    assert pa.align(vec, ["One.", "Two."], ["एक और दो।"]) == [("One. Two.", "एक और दो।", 1.0)]


def test_the_cache_encodes_each_text_once_ever(tmp_path):
    encode, calls = fake_vectors({"One.": "A", "Two.": "B"})
    path = tmp_path / "vectors.sqlite"
    first = pa.embedder(encode, pa.Cache(path, "m"))(["One.", "Two.", "One."])
    again = pa.embedder(encode, pa.Cache(path, "m"))(["Two.", "One."])  # a new run, the same file
    assert calls == [["One.", "Two."]]
    assert np.array_equal(first["One."], again["One."])


def test_the_cache_never_serves_another_models_vectors(tmp_path):
    encode, calls = fake_vectors({"One.": "A"})
    path = tmp_path / "vectors.sqlite"
    pa.embedder(encode, pa.Cache(path, "LaBSE"))(["One."])
    pa.embedder(encode, pa.Cache(path, "other"))(["One."])
    assert calls == [["One."], ["One."]]


def test_a_batch_embeds_its_english_once_however_many_languages_it_pairs_with():
    meaning = {"One.": "A", "Two.": "B", "एक।": "A", "दो।": "B", "एक.": "A", "दोन.": "B"}
    encode, calls = fake_vectors(meaning)
    group = {"prid": "1", "date": "D", "byLang": {
        "en": {"title": "", "body": "One. Two."}, "hi": {"title": "", "body": "एक। दो।"}, "mr": {"title": "", "body": "एक. दोन."}}}
    rows = list(pa.pairs_of([("delhi-en", group)], pa.embedder(encode)))
    sent = [t for call in calls for t in call]
    assert sent.count("One.") == 1 and sent.count("Two.") == 1
    assert [(r["lang"], r["en"], r["text"]) for r in rows] == [("hi", "One.", "एक।"), ("hi", "Two.", "दो।"), ("mr", "One.", "एक."), ("mr", "Two.", "दोन.")]
    assert rows[0]["office"] == "delhi-en" and rows[0]["prid"] == "1"


def test_a_document_pair_is_aligned_once_from_whichever_side_it_came():
    # Delhi's English with its Marathi, and Mumbai's Marathi with its English, are one pair of documents.
    meaning = {"One.": "A", "एक.": "A"}
    encode, _ = fake_vectors(meaning)
    delhi = {"prid": "10", "date": "D", "byLang": {"en": {"prid": "10", "title": "", "body": "One."}, "mr": {"prid": "20", "title": "", "body": "एक."}}}
    mumbai = {"prid": "20", "date": "D", "byLang": {"mr": {"prid": "20", "title": "", "body": "एक."}, "en": {"prid": "10", "title": "", "body": "One."}}}
    seen = set()
    first = list(pa.pairs_of([("delhi-en", delhi)], pa.embedder(encode), seen))
    again = list(pa.pairs_of([("mumbai-mr", mumbai)], pa.embedder(encode), seen))
    assert [(r["office"], r["text"]) for r in first] == [("delhi-en", "एक.")]
    assert again == []
    # Each pair names both of its documents.
    assert (first[0]["en_prid"], first[0]["text_prid"]) == ("10", "20")


def test_blank_lines_in_a_pairs_file_are_skipped():
    # An office with no releases that month wrote a pairs.jsonl holding one empty line.
    assert list(pa.groups_in(["", '{"prid": "1"}', "\n"])) == [{"prid": "1"}]
