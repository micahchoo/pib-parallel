# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["sentence-transformers", "numpy"]
# ///
"""Sentence pairs from PIB release groups (fetch.ts pairs.jsonl).

Each release and its translation are split into sentences, embedded with LaBSE
and aligned in order: 1-1, 1-2 and 2-1 matches and skips, by dynamic
programming over cosine similarity, as Vecalign and Bertalign do. A pair is
kept only above MIN_SIM. Every pair carries the release IDs it came from, and
`numbers`: whether both sides hold the same numbers (null when neither has any).
Vectors are kept in a SQLite file keyed by model and sentence (PIB_EMBEDDINGS,
default ~/.cache/pib-parallel/embeddings.sqlite: keep it on a fast disk), so each sentence is embedded once, ever:
a change to how pairs are scored reruns in seconds, not hours. Releases go in
batches of BATCH, each embedded in one call, so a Delhi release's English is
embedded once however many translations it has. Tested in
test/align_test.py, on fake vectors.

    uv run align.py data/2025-11/*/pairs.jsonl > data/2025-11/sentences.jsonl

LaBSE does not know Manipuri, Mizo, Khasi or Tenyidei, and knows Konkani only
through Marathi; their pairs carry a lower confidence and must be checked.
"""
import json
import re
import sys

MIN_SIM = 0.70
UNSEEN = {"mni", "lus", "kha", "njm", "gom"}
SKIP = -0.3  # the score of leaving a sentence unaligned


# Words a period follows without ending a sentence. Titles were mined from the
# November 2025 pilot, where "Dr." alone split 996 English sentences in two.
TITLES = {
    "Dr", "Mr", "Mrs", "Ms", "Smt", "Shri", "Sh", "Kum", "Prof", "Sr", "St", "Lt", "Col", "Gen", "Maj", "Capt",
    "Brig", "Cdr", "Adm", "Hon", "Rs", "No", "Nos",
    "डॉ", "प्रो", "श्री", "श्रीमती", "सुश्री", "कु", "रु", "क्र",  # Devanagari
    "ড", "ডা",  # Bengali, Assamese
    "ਡਾ", "ਪ੍ਰੋ", "ਨੰ", "ਸ੍ਰੀ", "ਸ਼੍ਰੀ",  # Gurmukhi
    "ડૉ", "ડો", "પ્રો", "શ્રી", "રૂ",  # Gujarati
    "ଡ", "ଡ଼", "ପ୍ରୋ", "ଶ୍ରୀ", "ଟ",  # Odia
    "திரு", "திருமதி", "செல்வி", "ரூ",  # Tamil
    "డా", "రూ", "శ్రీ", "ప్రొ",  # Telugu
    "ಡಾ", "ಪ್ರೊ", "ರೂ", "ಶೇ", "ಶ್ರೀ", "ಪ್ರೈ", "ಲಿ",  # Kannada
    "ഡോ", "പ്രൊ", "രൂ", "ശ്രീ",  # Malayalam
}

# Initials, which PIB writes as English letter names ("एल. मुरुगन"). Marathi ends
# most sentences with "आहे.", as short as any initial, so a length rule cannot
# tell them apart; only a list can. Written in Devanagari, with and without a
# final virama and with the short e (ऎ) the southern scripts use, then carried
# to the other Brahmic scripts, whose Unicode blocks run parallel to it.
_LETTERS = ("ए बी सी डी ई एफ जी एच आई जे के एल एम एन ओ पी क्यू आर एस टी यू वी डब्ल्यू एक्स वाई जेड ज़ेड "
            "एफ् एच् एल् एम् एन् आर् एस् एक्स् जेड् ऎफ् ऎच् ऎल् ऎम् ऎन् ऎस् ऎक्स् ऎफ ऎच ऎल ऎम ऎन ऎस").split()
_SCRIPTS = (0x0980, 0x0A00, 0x0A80, 0x0B00, 0x0B80, 0x0C00, 0x0C80, 0x0D00)


def _carried(word: str, base: int) -> str | None:
    import unicodedata

    out = "".join(chr(ord(c) - 0x0900 + base) for c in word)
    return out if all(unicodedata.name(c, None) for c in out) else None


INITIALS = set(_LETTERS) | {w for base in _SCRIPTS for x in _LETTERS if (w := _carried(x, base))} | {
    "ਐੱਲ", "ਐੱਮ", "ਐੱਨ", "ਐੱਸ", "ਐੱਫ", "ਐੱਚ", "ਐੱਕਸ",  # Gurmukhi doubles the consonant
    "ஏ", "பி", "சி", "டி", "ஜி", "ஹெச்", "எச்", "ஐ", "ஜே", "கே", "க்யூ", "ஆர்", "யு", "யூ", "வி", "ஒய்", "இசட்", "ஜெட்", "எஃப்",
    "എൽ", "എം", "എൻ", "എസ്", "എഫ്", "എച്ച്", "ആർ", "കെ", "പി", "ജി", "ബി", "സി", "ഡി", "ടി", "വി",  # Malayalam chillu
}


def _ends(before: str, after: str) -> bool:
    """Whether a period between these two texts ends a sentence."""
    words = before.split()
    word = words[-1].lstrip("([\"'“‘") if words else ""
    if word in TITLES or word in INITIALS or re.fullmatch(r"[A-Z]", word):
        return False
    if re.fullmatch(r"[^\s.\d]+(?:\.[^\s.\d]+)+", word):  # कि.मी, H.E, सी.पी; never 17.92 or 29.10.2025
        return False
    # Only Latin has case: "etc. were". A digit proves nothing: many Indic
    # sentences open with the year.
    return not after[:1].islower()


def sentences(text: str) -> list[str]:
    """Split at sentence marks of every script PIB writes: . ? ! । ॥ ۔ ؟ and line ends."""
    out, start = [], 0
    for m in re.finditer(r"([.?!।॥۔؟]+)\s+|\n+", text):
        if m.group(1) == "." and not _ends(text[start : m.start()], text[m.end() :]):
            continue
        out.append(text[start : m.start() + len(m.group(1) or "")])
        start = m.end()
    out.append(text[start:])
    return [p.strip() for p in out if len(p.strip()) > 1 and re.search(r"\w", p)]


# English counts in millions, Indian languages in lakhs and crores: "6.3 million"
# is "63 लाख". Matched as a prefix of the word after the number, which takes
# case endings ("लाखांहून", "ಲಕ್ಷಕ್ಕೂ", "కోట్ల").
SCALES = [
    (10**5, ("lakh", "lac", "लाख", "লাখ", "লক্ষ", "ਲੱਖ", "લાખ", "ଲକ୍ଷ", "லட்ச", "లక్ష", "ಲಕ್ಷ", "ലക്ഷ", "لاکھ")),
    (10**7, ("crore", "करोड़", "करोड", "कोटी", "কোটি", "ਕਰੋੜ", "કરોડ", "କୋଟି", "கோடி", "కోట", "కోటి", "ಕೋಟಿ", "കോടി", "کروڑ")),
    (10**6, ("million", "ದಶಲಕ್ಷ", "मिलियन", "মিলিয়ন", "ਮਿਲੀਅਨ", "મિલિયન", "ମିଲିୟନ", "மில்லியன்", "మిలియన్", "ಮಿಲಿಯನ್", "മില്യ", "ملین")),
    (10**9, ("billion", "बिलियन", "বিলিয়ন", "ਬਿਲੀਅਨ", "બિલિયન", "ବିଲିୟନ", "பில்லியன்", "బిలియన్", "ಬಿಲಿಯನ್", "ബില്യ", "بلین")),
    (10**12, ("trillion",)),
]


def numbers(s: str) -> list[str]:
    """The numbers in a sentence as plain values: ASCII digits from any script, grouping commas
    dropped, and a scale word multiplied in."""
    s = "".join(str(int(c)) if c.isdecimal() else c for c in s)
    out = []
    for m in re.finditer(r"(\d+(?:,\d+)*(?:\.\d+)?)(?=\s*(\S*))", s):
        value = float(m.group(1).replace(",", ""))
        after = m.group(2).lower()
        value *= next((k for k, words in SCALES if after.startswith(words)), 1)
        out.append(str(int(value)) if value == int(value) else str(round(value, 6)))
    return sorted(out)


def numbers_agree(a: str, b: str) -> bool | None:
    """True when both sides hold the same numbers, False when not, None when neither has any."""
    na, nb = set(numbers(a)), set(numbers(b))
    return None if not na and not nb else na == nb


MODEL = "sentence-transformers/LaBSE"

# Languages LaBSE cannot read, aligned with LASER instead: English through LASER2,
# the language through its own LASER3 encoder, each with a cut set on PIB's gold
# title pairs to let through as many wrong titles as LaBSE's 0.70 does in Bengali
# (25%). Manipuri at 0.80 kept 64% of its gold titles; LaBSE at 0.70 kept 12%.
# LASER needs Python 3.10, so laser.py fills the cache and this script only reads it.
LASER = {"mni": ("mni_Beng", 0.80)}
LASER_ENGLISH = "LASER2:eng_Latn"


def laser_key(lang: str) -> str:
    return f"LASER3:{LASER[lang][0]}"
BATCH = 32  # release groups embedded in one call


class Cache:
    """Sentence vectors on disk, keyed by model and text: each sentence is embedded once, ever.
    Changing how pairs are scored then costs no embedding at all."""

    def __init__(self, path, model: str):
        import sqlite3

        self.db = sqlite3.connect(str(path))
        # A write-ahead log and no sync per commit: with the default journal every
        # batch waited on the disk, and on spinning disks the run stalled at 3%
        # GPU. The cache can always be rebuilt, so a crash costs only its last batch.
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS v (k TEXT PRIMARY KEY, b BLOB)")
        self.model = model

    def _key(self, text: str) -> str:
        import hashlib

        return hashlib.sha1(f"{self.model}\0{text}".encode()).hexdigest()

    def get(self, texts: list[str]) -> dict:
        import numpy as np

        keys = {self._key(t): t for t in texts}
        out = {}
        items = list(keys)
        for i in range(0, len(items), 500):
            chunk = items[i : i + 500]
            for k, b in self.db.execute(f"SELECT k, b FROM v WHERE k IN ({','.join('?' * len(chunk))})", chunk):
                out[keys[k]] = np.frombuffer(b, dtype=np.float32)
        return out

    def put(self, vectors: dict) -> None:
        import numpy as np

        self.db.executemany("INSERT OR REPLACE INTO v VALUES (?, ?)", [(self._key(t), np.asarray(v, dtype=np.float32).tobytes()) for t, v in vectors.items()])
        self.db.commit()


def embedder(encode, cache: Cache | None = None):
    """Texts to unit vectors, encoding only what the cache does not hold, each text once."""

    def vectors(texts: list[str]) -> dict:
        unique = list(dict.fromkeys(texts))
        have = cache.get(unique) if cache else {}
        missing = [t for t in unique if t not in have]
        if missing:
            new = dict(zip(missing, encode(missing)))
            if cache:
                cache.put(new)
            have.update(new)
        return have

    return vectors


def side(texts: list[str]) -> list[str]:
    """Every text align() reads on one side: each sentence, and each pair of neighbours."""
    return texts + [a + " " + b for a, b in zip(texts, texts[1:])]


def needed(src: list[str], tgt: list[str]) -> list[str]:
    """Every text align() reads: each sentence, and each pair of neighbours for 1-2 and 2-1 matches."""
    return side(src) + side(tgt)


def align(vec: dict, src: list[str], tgt: list[str], vec_tgt: dict | None = None) -> list[tuple[str, str, float]]:
    """Sentence pairs in order; `vec_tgt` holds the target side's vectors when its encoder differs."""
    import numpy as np

    if not src or not tgt:
        return []
    vt = vec if vec_tgt is None else vec_tgt
    # Every similarity the search can ask for, three matrix products up front:
    # looked up cell by cell it was the slowest part of a run once the vectors
    # came from the GPU (6% busy).
    stack = lambda texts: np.stack([vec[t] for t in texts]) if texts else np.zeros((0, len(vec[src[0]])))
    stack_t = lambda texts: np.stack([vt[t] for t in texts]) if texts else np.zeros((0, len(vt[tgt[0]])))
    S1, T1 = stack(src), stack_t(tgt)
    S2, T2 = stack([a + " " + b for a, b in zip(src, src[1:])]), stack_t([a + " " + b for a, b in zip(tgt, tgt[1:])])
    one, two_one, one_two = (S1 @ T1.T).tolist(), (S2 @ T1.T).tolist(), (S1 @ T2.T).tolist()
    n, m = len(src), len(tgt)
    best = np.full((n + 1, m + 1), -1e9)
    back = {}
    best[0, 0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if best[i, j] <= -1e9:
                continue
            moves = []
            if i < n and j < m:
                moves.append((1, 1, one[i][j]))
            if i + 1 < n and j < m:
                moves.append((2, 1, two_one[i][j]))
            if i < n and j + 1 < m:
                moves.append((1, 2, one_two[i][j]))
            if i < n:
                moves.append((1, 0, SKIP))
            if j < m:
                moves.append((0, 1, SKIP))
            for di, dj, score in moves:
                if best[i, j] + score > best[i + di, j + dj]:
                    best[i + di, j + dj] = best[i, j] + score
                    back[(i + di, j + dj)] = (i, j, score)
    pairs, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj, score = back[(i, j)]
        if i - pi and j - pj:
            pairs.append((" ".join(src[pi:i]), " ".join(tgt[pj:j]), score))
        i, j = pi, pj
    return pairs[::-1]


def groups_in(lines):
    """Release groups from the lines of a pairs.jsonl; an office with no releases writes none."""
    return (json.loads(line) for line in lines if line.strip())


def pairs_of(groups: list[tuple[str, dict]], vectors, seen: set | None = None, laser: dict | None = None):
    """Sentence pairs for a batch of (office, release group), with the whole batch embedded in one call.
    A document pair already in `seen` is skipped: Delhi's English with its Marathi and Mumbai's
    Marathi with its English are the same two documents. A language in LASER is aligned with
    `laser[lang]` = (English vectors, its own vectors, cut), and is an error without it."""
    laser = laser or {}
    seen = set() if seen is None else seen
    jobs = []
    for office, group in groups:
        by = group["byLang"]
        # English is the pivot; a group without it has nothing to pair against.
        if "en" not in by:
            continue
        en = sentences(by["en"]["title"] + "\n" + by["en"]["body"])
        for lang, doc in by.items():
            if lang == "en":
                continue
            pair = (by["en"].get("prid"), doc.get("prid"))
            if None not in pair:
                if pair in seen:
                    continue
                seen.add(pair)
            jobs.append((office, group, lang, pair, en, sentences(doc["title"] + "\n" + doc["body"])))
    for *_, lang, _, _, _ in jobs:
        if lang in LASER and lang not in laser:
            raise KeyError(f"{lang} is aligned with LASER: run laser.py on these files first")
    vec = vectors([t for *_, lang, _, en, tgt in jobs if lang not in laser for t in needed(en, tgt)])
    own = {lang: (en_v([t for *_, l, _, en, _ in jobs if l == lang for t in side(en)]),
                  tx_v([t for *_, l, _, _, tgt in jobs if l == lang for t in side(tgt)]), cut)
           for lang, (en_v, tx_v, cut) in laser.items()}
    for office, group, lang, (en_prid, text_prid), en, tgt in jobs:
        v_en, v_tx, cut = own.get(lang, (vec, None, MIN_SIM))
        for s, t, sim in align(v_en, en, tgt, v_tx):
            if sim >= cut:
                # Recorded, not yet a filter: the measuring stick decides that.
                yield {"lang": lang, "en": s, "text": t, "sim": round(sim, 3), "numbers": numbers_agree(s, t),
                       "confidence": "low" if lang in UNSEEN else "normal",
                       "prid": group["prid"], "en_prid": en_prid, "text_prid": text_prid,
                       "date": group.get("date", ""), "office": office}


if __name__ == "__main__":
    import os

    from sentence_transformers import SentenceTransformer

    import torch

    # On a GPU, half precision: on the Radeon 8060S fp32 ran 158 sentences/s and
    # fp16 1,734, with every vector within cosine 0.9995 of fp32. Its vectors are
    # cached under their own key and never mix with fp32 ones.
    gpu = torch.cuda.is_available()
    model = SentenceTransformer(MODEL, device="cuda" if gpu else "cpu")
    if gpu:
        model = model.half()
    print(f"LaBSE on {torch.cuda.get_device_name(0) + ', fp16' if gpu else 'CPU'} (torch {torch.__version__})", file=sys.stderr)
    # A machine-local cache, by default where caches go, not beside the corpus.
    path = os.environ.get("PIB_EMBEDDINGS", os.path.expanduser("~/.cache/pib-parallel/embeddings.sqlite"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cache = Cache(path, MODEL + ("@fp16" if gpu else ""))
    vectors = embedder(lambda texts: model.encode(texts, normalize_embeddings=True, batch_size=256 if gpu else 64).astype("float32"), cache)

    def made_by_laser_py(key):
        def encode(texts):
            raise KeyError(f"{len(texts)} sentences have no {key} vector: run laser.py on these files first")
        return encode

    laser = {lang: (embedder(made_by_laser_py(LASER_ENGLISH), Cache(path, LASER_ENGLISH)),
                    embedder(made_by_laser_py(laser_key(lang)), Cache(path, laser_key(lang))), cut)
             for lang, (_, cut) in LASER.items()}
    batch: list[tuple[str, dict]] = []
    seen: set = set()

    def flush():
        for row in pairs_of(batch, vectors, seen, laser):
            print(json.dumps(row, ensure_ascii=False), flush=False)
        sys.stdout.flush()
        batch.clear()

    for path in sys.argv[1:]:
        office = path.split("/")[-2]
        for group in groups_in(open(path)):
            batch.append((office, group))
            if len(batch) >= BATCH:
                flush()
    flush()
