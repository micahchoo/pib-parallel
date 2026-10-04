# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["pyarrow"]
# ///
"""The dataset from one crawled month: two Parquet files, as published on Hugging Face.

    uv run package.py data/2025-11

reads data/2025-11/*/pairs.jsonl (fetch.ts), sentences.jsonl (align.py) and,
if present, copies.jsonl (copies.ts), and writes data/2025-11/release/:

  sentences.parquet   one row per distinct sentence pair. A pair PIB repeats
                      across releases ("Friends," opens hundreds of speeches)
                      is one row with its count in `occurrences`.
  documents.parquet   one row per pair of documents: an English release and
                      one translation, each with its PRID. A pair found from
                      both sides (Delhi's English with its Marathi, Mumbai's
                      Marathi with its English) is one row.
"""
import json
import pathlib
import re
import sys

MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def posted(dateline: str) -> tuple[str, str]:
    """'28 NOV 2025 6:07PM by PIB Delhi' -> ('2025-11-28', 'PIB Delhi'); ('', '') when PIB wrote none."""
    m = re.match(r"(\d{1,2}) ([A-Z]{3}) (\d{4})[^b]*(?:by (.+))?", dateline.strip())
    if not m or m.group(2) not in MONTHS:
        return "", ""
    return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}", (m.group(4) or "").strip()


def fold(pairs, copies: dict) -> list[dict]:
    """Distinct sentence pairs, each with how often it occurred and, where it was sampled, whether
    PIB's text is a near copy of Google Translate's."""
    rows: dict[tuple, dict] = {}
    for p in pairs:
        key = (p["lang"], p["en"], p["text"])
        if key in rows:
            rows[key]["occurrences"] += 1
            continue
        date, by = posted(p.get("date", ""))
        rows[key] = {
            "lang": p["lang"], "en": p["en"], "text": p["text"], "similarity": p["sim"], "numbers_agree": p["numbers"],
            "confidence": p["confidence"], "google_copy": copies.get(key), "occurrences": 1,
            "en_prid": p["en_prid"], "text_prid": p["text_prid"], "office": p["office"], "date": date, "posted_by": by,
        }
    return list(rows.values())


def documents(groups) -> list[dict]:
    """One row per (English release, translation), from (office, release group) in crawl order."""
    seen, out = set(), []
    for office, g in groups:
        by = g["byLang"]
        if "en" not in by:
            continue
        date, poster = posted(g.get("date", ""))
        for lang, doc in by.items():
            key = (by["en"].get("prid"), doc.get("prid"))
            if lang == "en" or key in seen:
                continue
            seen.add(key)
            out.append({
                "lang": lang, "en_prid": key[0], "text_prid": key[1], "en_title": by["en"]["title"], "en_body": by["en"]["body"],
                "title": doc["title"], "body": doc["body"], "ministry": g.get("ministry", ""), "office": office,
                "date": date, "posted_by": poster,
            })
    return out


def jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


if __name__ == "__main__":
    import pyarrow as pa
    import pyarrow.parquet as pq

    month = pathlib.Path(sys.argv[1])
    out = month / "release"
    out.mkdir(exist_ok=True)
    copies_file = month / "copies.jsonl"
    copies = {(c["lang"], c["en"], c["text"]): c["google_copy"] for c in jsonl(copies_file)} if copies_file.exists() else {}
    sentences = fold(jsonl(month / "sentences.jsonl"), copies)
    # The same order align.py read the passes in, so a document is credited to the same office as its sentences.
    groups = [(p.parent.name, g) for p in sorted(month.glob("*/pairs.jsonl")) if p.parent.name != "bench" for g in jsonl(p)]
    docs = documents(groups)
    for name, rows in (("sentences", sentences), ("documents", docs)):
        pq.write_table(pa.Table.from_pylist(rows), out / f"{name}.parquet", compression="zstd")
        print(f"{name}: {len(rows)} rows -> {out / name}.parquet")
