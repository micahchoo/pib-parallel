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

english = None
for lang, (en, tx) in texts.items():
    for key, laser_lang, wanted in ((al.LASER_ENGLISH, "eng_Latn", en), (al.laser_key(lang), al.LASER[lang][0], tx)):
        cache = al.Cache(path, key)
        have = cache.get(sorted(wanted))
        missing = [t for t in sorted(wanted) if t not in have]
        if not missing:
            continue
        if laser_lang == "eng_Latn":
            english = english or LaserEncoderPipeline(lang="eng_Latn")
            encoder = english
        else:
            encoder = LaserEncoderPipeline(lang=laser_lang)
        for i in range(0, len(missing), 512):
            chunk = missing[i : i + 512]
            cache.put(dict(zip(chunk, encoder.encode_sentences(chunk, normalize_embeddings=True))))
        print(f"{key}: {len(missing)} new vectors for {lang}", file=sys.stderr)
