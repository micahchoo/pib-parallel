# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["laser_encoders", "requests", "numpy"]
# ///
"""LASER vectors for the languages align.py reads with LASER (align.py#LASER), into its cache.

    uv run laser.py data/2025-11/*/pairs.jsonl        then align.py on the same files

LASER needs Python 3.10 (fairseq 0.12 fails on 3.11's dataclasses), so it runs
here, apart from align.py, and the shared cache carries the vectors across.
English is encoded with LASER2 and each language with its LASER3 encoder, the
pair the LASER3 encoders were trained to share a space with.
"""
import argparse
import importlib.util
import os
import pathlib
import sys

import torch

# LASER's checkpoints keep their options as an argparse.Namespace. PyTorch 2.6
# refuses that by default; this allows that one class, not arbitrary code.
torch.serialization.add_safe_globals([argparse.Namespace])
from laser_encoders import LaserEncoderPipeline

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("align", pathlib.Path(__file__).parent / "align.py")
al = importlib.util.module_from_spec(spec)
spec.loader.exec_module(al)

path = os.environ.get("PIB_EMBEDDINGS", os.path.expanduser("~/.cache/pib-parallel/embeddings.sqlite"))
os.makedirs(os.path.dirname(path), exist_ok=True)
texts = {lang: (set(), set()) for lang in al.LASER}
for f in sys.argv[1:]:
    for group in al.groups_in(open(f)):
        by = group["byLang"]
        if "en" not in by:
            continue
        en = al.sentences(by["en"]["title"] + "\n" + by["en"]["body"])
        for lang, doc in by.items():
            if lang in al.LASER:
                texts[lang][0].update(al.side(en))
                texts[lang][1].update(al.side(al.sentences(doc["title"] + "\n" + doc["body"])))

# Two workers can share one run: LASER_REVERSE=1 takes the list from its end, and
# every chunk is checked against the cache first, so neither encodes what the
# other has done, and a stopped run resumes where it stopped. LASER_FP16=1 puts
# the encoder in half precision: on the Radeon 8060S, 138 Manipuri sentences/s
# against 23 in full precision, every vector within cosine 0.9994 of the CPU's.
# Those vectors share the CPU's key: for LaBSE a difference that size changed
# no pair, and two keys would only mix the same vectors by another route.
# LASER_ONLY=en or tx limits a worker to one side. The GPU gains on the LASER3
# encoders (transformers) and almost nothing on LASER2, an LSTM, which ran at
# 23 sentences/s there: so the CPU takes English and the GPU the language.
only = os.environ.get("LASER_ONLY", "")
reverse = os.environ.get("LASER_REVERSE") == "1"
fp16 = os.environ.get("LASER_FP16") == "1"
encoders = {}


def encoder_for(laser_lang):
    if laser_lang not in encoders:
        encoders[laser_lang] = LaserEncoderPipeline(lang=laser_lang)
        if fp16:
            encoders[laser_lang].encoder.encoder.half()
    return encoders[laser_lang]


for lang, (en, tx) in texts.items():
    for side, key, laser_lang, wanted in (("en", al.LASER_ENGLISH, "eng_Latn", en), ("tx", al.laser_key(lang), al.LASER[lang][0], tx)):
        if only and side != only:
            continue
        cache = al.Cache(path, key)
        order = sorted(wanted, reverse=reverse)
        have = cache.get(order)
        missing = [t for t in order if t not in have]
        made = 0
        for i in range(0, len(missing), 512):
            chunk = [t for t in missing[i : i + 512] if t not in cache.get(missing[i : i + 512])]
            if chunk:
                cache.put(dict(zip(chunk, encoder_for(laser_lang).encode_sentences(chunk, normalize_embeddings=True))))
                made += len(chunk)
        if made:
            print(f"{key}: {made} new vectors for {lang}", file=sys.stderr)
