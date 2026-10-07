# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["pyarrow"]
# ///
"""The Hugging Face card, from card/template.md and every month in a data folder.

    uv run card.py data > data/hf/README.md

A month is data/<YYYY-MM>/ with release/{sentences,documents}.parquet; it becomes
one split of each config, named like `nov2025`: a name YAML cannot read as a
number (`2025_11` reads as 202511). A month with only copies.jsonl, a sample
that was never packaged, adds a column to the copy-rate table and nothing else.
"""
import calendar
import json
import pathlib
import sys

NAMES = {
    "hi": "Hindi", "ur": "Urdu", "gu": "Gujarati", "mr": "Marathi", "ml": "Malayalam", "kn": "Kannada", "pa": "Punjabi",
    "te": "Telugu", "bn": "Bengali", "or": "Odia", "as": "Assamese", "ta": "Tamil", "gom": "Konkani", "ne": "Nepali",
    "kha": "Khasi", "mni": "Manipuri", "lus": "Mizo", "njm": "Tenyidei",
}


def split_name(month: str) -> str:
    """'2025-11' -> 'nov2025'."""
    year, m = month.split("-")
    return calendar.month_abbr[int(m)].lower() + year


def label(month: str) -> str:
    """'2025-11' -> 'November 2025'."""
    year, m = month.split("-")
    return f"{calendar.month_name[int(m)]} {year}"


def configs(months: list[str]) -> str:
    out = []
    for config, default in (("sentences", True), ("documents", False)):
        out.append(f"- config_name: {config}")
        if default:
            out.append("  default: true")
        out.append("  data_files:")
        for m in months:
            out += [f"  - split: {split_name(m)}", f"    path: {config}/{m}.parquet"]
    return "\n".join(out)


def office_label(office: str) -> str:
    city, lang = office.rsplit("-", 1)
    return f"{city.replace('-', ' ').title()}, {NAMES.get(lang, lang)}"


def rate(k: int, n: int) -> str:
    return f"{100 * k / n:.0f}%" + ("" if n >= 100 else f" (of {n})")


def copy_table(copies: dict[str, list[dict]]) -> str:
    """Rows: each regional office's own language, then Delhi's translations by language; a column per month."""
    months = sorted(copies)
    cells: dict[tuple, dict[str, list[int]]] = {}
    for m, rows in copies.items():
        for r in rows:
            key = ("delhi", r["lang"]) if r["office"] == "delhi-en" else ("office", r["office"])
            if key[0] == "office" and not r["office"].endswith("-" + r["lang"]):
                continue  # a regional pass's stray language, such as Chandigarh's Hindi
            c = cells.setdefault(key, {}).setdefault(m, [0, 0])
            c[0] += r["google_copy"]
            c[1] += 1
    head = "| Office, language | " + " | ".join(label(m) for m in months) + " |"
    lines = [head, "| --- |" + " --- |" * len(months)]
    for key in sorted(cells, key=lambda k: (k[0] == "delhi", k[1])):
        name = office_label(key[1]) if key[0] == "office" else f"Delhi's {NAMES.get(key[1], key[1])} translations"
        row = [rate(*cells[key][m]) if m in cells[key] else "" for m in months]
        lines.append(f"| {name} | " + " | ".join(row) + " |")
    return "\n".join(lines)


def month_stats(month_dir: pathlib.Path) -> dict:
    import pyarrow.parquet as pq

    s = pq.read_table(month_dir / "release" / "sentences.parquet").to_pylist()
    d = pq.read_table(month_dir / "release" / "documents.parquet").to_pylist()
    langs: dict[str, list[int]] = {}
    for r in s:
        v = langs.setdefault(r["lang"], [0, 0, 0, 0])
        v[0] += 1
        v[1] += r["similarity"] >= 0.85
        v[3] = r["confidence"] == "low"
    for r in d:
        langs.setdefault(r["lang"], [0, 0, 0, 0])[2] += 1
    known = [r["google_copy"] for r in s if r["google_copy"] is not None]
    return {"langs": langs, "pairs": len(s), "high": sum(v[1] for v in langs.values()), "docs": len(d),
            "releases": len({r["en_prid"] for r in d}), "known": len(known), "copies": sum(known)}


def language_table(stats: dict) -> str:
    lines = ["| Language | Code | Sentence pairs | Similarity ≥ 0.85 | Document pairs |", "| --- | --- | --- | --- | --- |"]
    for code, (n, high, docs, low) in sorted(stats["langs"].items(), key=lambda kv: -kv[1][0]):
        name = NAMES.get(code, code) + (" (low confidence)" if low else "")
        lines.append(f"| {name} | `{code}` | {n:,} | {high:,} | {docs:,} |")
    lines.append(f"| **All** | | **{stats['pairs']:,}** | **{stats['high']:,}** | **{stats['docs']:,}** |")
    return "\n".join(lines)


def size_category(n: int) -> str:
    for limit, name in ((10**5, "10K<n<100K"), (10**6, "100K<n<1M"), (10**7, "1M<n<10M")):
        if n < limit:
            return name
    return "10M<n<100M"


def card(template: str, data: pathlib.Path) -> str:
    months = sorted(p.parent.parent.name for p in data.glob("*/release/sentences.parquet"))
    stats = {m: month_stats(data / m) for m in months}
    copies = {p.parent.name: [json.loads(l) for l in open(p) if l.strip()] for p in sorted(data.glob("*/copies.jsonl"))}
    total = sum(s["pairs"] for s in stats.values())
    langs = sorted({c for s in stats.values() for c in s["langs"]}, key=lambda c: -sum(s["langs"].get(c, [0])[0] for s in stats.values()))
    month_rows = ["| Split | Month | Sentence pairs | Document pairs | English releases |", "| --- | --- | --- | --- | --- |"]
    month_rows += [f"| `{split_name(m)}` | {label(m)} | {stats[m]['pairs']:,} | {stats[m]['docs']:,} | {stats[m]['releases']:,} |" for m in months]
    per_month = "\n\n".join(f"### {label(m)}\n\n" + language_table(stats[m]) for m in reversed(months))
    known = sum(s["known"] for s in stats.values())
    fills = {
        "{{configs}}": configs(months),
        "{{languages_yaml}}": "\n".join(f"- {c}" for c in ["en"] + langs),
        "{{size}}": size_category(total),
        "{{months}}": "\n".join(month_rows),
        "{{per_month}}": per_month,
        "{{copies}}": copy_table(copies),
        "{{total_pairs}}": f"{total:,}",
        "{{total_docs}}": f"{sum(s['docs'] for s in stats.values()):,}",
        "{{month_count}}": f"{len(months)} month" + ("s" if len(months) != 1 else ""),
        "{{languages_count}}": str(len(langs)),
        "{{first_split}}": split_name(months[-1]) if months else "",
        "{{known}}": f"{known:,}",
        "{{known_copies}}": f"{sum(s['copies'] for s in stats.values()):,}",
    }
    for k, v in fills.items():
        template = template.replace(k, v)
    return template


if __name__ == "__main__":
    data = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    print(card((pathlib.Path(__file__).parent / "card" / "template.md").read_text(), data), end="")
