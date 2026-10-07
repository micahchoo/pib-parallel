# The audit that stops a month being published with a contact detail in it. It
# must not share the fetcher's patterns: the first audit did, and missed what
# they missed.
#
#   uv run --no-project --with pytest pytest -p no:cacheprovider test/audit_test.py
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("audit", Path(__file__).parent.parent / "audit.py")
au = importlib.util.module_from_spec(spec)
spec.loader.exec_module(au)


def test_the_forms_that_once_slipped_through_are_found():
    leaked = [
        "TRAI નો ટેલિફોન નંબર + 91-11-20907757 પર",       # a space after the plus
        "اورفون نمبر -23000761 +91-40 پر",                  # right-to-left order
        "ईमेल: adv.ca@trai. gov.in या",                     # a space in the domain
        "ای میل ( csm-upsc [at] nic [dot] in )",            # spelled out
    ]
    assert [bool(au.leaks(t)) for t in leaked] == [True, True, True, True]


def test_placeholders_handles_tables_and_links_are_not_leaks():
    clean = [
        "ईमेल: <email> या फ़ोन <phone> पर",
        "X Handles: @PIB_Goa, @PIBMumbai",
        "General Medicine   21741389   183725535263",
        "https://doi.org/10.1016/S0140-6736(21)02143-7",
        # False alarms of the first version, November 2025: a slogan, a price, a handle at a sentence end.
        "towards Viksit Bharat @2047.",
        "kits @ Rs. 500 each",
        "posted by @narendramodi. The Prime Minister said",
    ]
    assert [au.leaks(t) for t in clean] == [[]] * len(clean)
