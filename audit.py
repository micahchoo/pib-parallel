# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["pyarrow"]
# ///
"""Stops a month being published with a contact detail left in it.

    uv run audit.py data/2025-11        exit 1, with the leaks listed, if any text holds one

Independent of fetch.ts's patterns on purpose: the first audit shared them and
missed what they missed ("+ 91-11-...", "-23000761 +91-40", "trai. gov.in").
It looks for signs rather than exact shapes: a +91 however spaced; an @ or
[at] after a word and before a dot; a mobile or a landline number. Digits
inside a link are not read. Every script's digits count as digits.
"""
import re
import sys
import unicodedata

URL = re.compile(r"\S*(?:https?://|www\.|doi\.org/)\S*", re.I)
SIGNS = {
    "+91": re.compile(r"\+\s?91"),
    # A plain @ joins the address with no space ("Viksit Bharat @2047", "@ Rs.", "@narendramodi." are
    # not addresses); the domain starts with a letter and has letters after its dot, which may be spaced.
    "email": re.compile(r"[\w.-](?:@|\s?\[at\]\s?)[a-z][\w-]*(?:\.\s?|\s?\[dot\]\s?)[a-z]{2,}", re.I),
    "mobile": re.compile(r"(?<![\d.,])[6-9]\d{4}[\s-]?\d{5}(?![\d.,])"),
    "landline": re.compile(r"(?<![\d.,])0\d{2,4}[\s-]\d{6,8}(?![\d.,])"),
}


def ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


def leaks(text: str) -> list[str]:
    """Every sign of a contact detail in the text, as 'kind: match'."""
    t = URL.sub(" ", ascii_digits(text))
    return [f"{kind}: {m.group()}" for kind, rx in SIGNS.items() for m in rx.finditer(t)]


if __name__ == "__main__":
    import pathlib

    import pyarrow.parquet as pq

    release = pathlib.Path(sys.argv[1]) / "release"
    fields = {"sentences": ("en", "text"), "documents": ("en_title", "en_body", "title", "body")}
    found = []
    for name, cols in fields.items():
        for row in pq.read_table(release / f"{name}.parquet", columns=[*cols, "lang"]).to_pylist():
            for col in cols:
                found += [f"{name}.{col} [{row['lang']}] {leak}" for leak in leaks(row[col] or "")]
    print(f"{len(found)} signs of a contact detail in {release}")
    for f in found[:30]:
        print("  " + f)
    sys.exit(1 if found else 0)
