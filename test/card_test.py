# The Hugging Face card's generated parts.
#
#   uv run --no-project --with pytest --with pyyaml pytest -p no:cacheprovider test/card_test.py
import importlib.util
import sys
from pathlib import Path

import yaml

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("card", Path(__file__).parent.parent / "card.py")
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)


def test_every_split_name_reads_back_as_text_not_a_number():
    # "2025_11" in YAML is the number 202511, and datasets then fails on it.
    parsed = yaml.safe_load(cd.configs(["2019-07", "2025-11"]))
    splits = [f["split"] for c in parsed for f in c["data_files"]]
    assert splits == ["jul2019", "nov2025", "jul2019", "nov2025"]
    assert all(isinstance(s, str) for s in splits)
    assert parsed[0]["default"] is True and parsed[1]["data_files"][1]["path"] == "documents/2025-11.parquet"


def test_the_copy_table_has_a_column_per_month_and_skips_a_passs_stray_language():
    row = lambda office, lang, copy: {"office": office, "lang": lang, "google_copy": copy}
    copies = {
        "2018-11": [row("kolkata-bn", "bn", False)] * 100,
        "2025-11": [row("kolkata-bn", "bn", False)] * 88 + [row("chandigarh-pa", "hi", True)] * 5 + [row("delhi-en", "hi", True)] * 29 + [row("delhi-en", "hi", False)] * 71,
    }
    table = cd.copy_table(copies).splitlines()
    assert table[0] == "| Office, language | November 2018 | November 2025 |"
    assert "| Kolkata, Bengali | 0% | 0% (of 88) |" in table
    assert "| Delhi's Hindi translations |  | 29% |" in table
    assert not any("Chandigarh" in line for line in table)
