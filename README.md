# pib-parallel

A pipeline that turns the Press Information Bureau's press releases into parallel text: English beside each official translation, by sentence and by document, every pair traceable to the releases it came from.

The Press Information Bureau (PIB, [pib.gov.in](https://www.pib.gov.in)) is the Government of India's press office. It publishes each release in English and links the same release translated by its offices: 15 of India's 22 scheduled languages, and Mizo, Khasi and Tenyidei. Office and language codes are in `offices.tsv`. Earlier PIB corpora (CVIT-PIB, PMIndia) end around 2019. This one can fetch any month since then, from every office, and it records each pair's release IDs.

Months are published as a dataset, one split per month: [huggingface.co/datasets/micahchoo/pib-parallel](https://huggingface.co/datasets/micahchoo/pib-parallel). Its card has the numbers and the limits. Use this repository to fetch other months.

## What you need

- [Bun](https://bun.sh) for the fetcher and the copy check.
- [uv](https://docs.astral.sh/uv/) for the aligner and the packager.
- Optional: a GPU. On an AMD Radeon 8060S the aligner ran 11 times faster in half precision (see "Run it on a GPU").
- Optional: a Google Cloud Translation key, only for the copy check.

## Use it

**1. Fetch a month.** `crawl.sh` asks PIB's own list page for every release each office published that month, then downloads each release and the translations it links.

```sh
./crawl.sh 2025-11
```

It writes `data/2025-11/<office>/pairs.jsonl`, one row per release with every language PIB published it in, each side with its own release ID (PRID). It fetches one page at a time, 1.5 seconds apart (`PIB_DELAY`), and names itself and this repository in every request. Every page is kept in `data/html`, so a rerun or a crash costs nothing. November 2025, every office, was about 10,000 pages: five to six hours at the default pace.

At the end of each office, a line says how many releases link a translation. PIB has linked them on every office's pages since 2020; before that some offices did not (see the dataset card). Where none are linked, this method finds no pairs.

**2. Align the sentences.**

```sh
uv run align.py data/2025-11/*/pairs.jsonl > data/2025-11/sentences.jsonl
```

Each release is cut into sentences, at the marks of every script PIB writes, but not after a title ("Dr.", "डॉ.", "திரு.") or an initial written as a letter name ("एल.", "ಎಲ್."). LaBSE embeds every sentence, and dynamic programming matches them in order, one to one, one to two or two to one. Pairs above a similarity of 0.70 are kept. Each pair records its similarity, whether its numbers agree (lakh, crore, million and billion read as values), and its two PRIDs. A pair of documents found from both sides, Delhi's English with its Marathi and Mumbai's Marathi with its English, is aligned once.

LaBSE does not know Manipuri, Mizo, Khasi or Tenyidei, and knows Konkani only through Marathi. Their pairs are marked `confidence: low`. Manipuri is aligned with LASER instead (English through LASER2, Manipuri through its LASER3 encoder), cut at 0.80: on PIB's own title pairs, LASER3 found the right English title for 77% of Manipuri ones against LaBSE's 55%, and in November 2025 it gave 5,596 pairs where LaBSE gave 763. LASER needs Python 3.10, so `laser.py` fills the vector cache first and `align.py` reads it:

```sh
uv run -p 3.10 laser.py data/2025-11/*/pairs.jsonl
uv run align.py data/2025-11/*/pairs.jsonl > data/2025-11/sentences.jsonl
```

Sentence vectors are cached in `~/.cache/pib-parallel/embeddings.sqlite` (`PIB_EMBEDDINGS`), so a rerun only embeds new sentences. Keep the cache on a fast disk.

**3. Measure how much is Google Translate (optional).**

```sh
GOOGLE_TRANSLATE_API_KEY=... bun copies.ts data/2025-11/sentences.jsonl 100
```

For up to 100 pairs per office and language, Google translates the English. A pair whose PIB text is within chrF 90 of Google's is a copy: two independent translations of one sentence almost never come that close. It prints a rate per office with a 95% interval and writes `copies.jsonl` with each sampled pair's flag, never Google's text, whose terms forbid passing it on. It refuses to send more than `GT_BUDGET` new characters (default 300,000, about $6), and caches every answer.

The rate is a lower bound on machine text: heavier editing, or another engine, passes as "not a copy".

**4. Build the dataset.**

```sh
uv run package.py data/2025-11
```

It writes `data/2025-11/release/sentences.parquet`, one row per distinct sentence pair with how often it occurred, and `documents.parquet`, one row per pair of documents.

**5. Check, and publish.** `audit.py` searches the packaged month for contact details again, with its own patterns rather than the fetcher's, and exits 1 if it finds any: an audit that shared the fetcher's patterns once missed what they missed. `publish.sh` runs a crawled month through every step, rebuilding it from the page cache with the current parser first, and stops at the first failure:

```sh
./publish.sh 2019-07     # rebuild, align, copies, package, audit, card.py, upload.py
```

`regional.sh` fetches every month of the offices that publish little in their own language (Nepali from Gangtok, Khasi from Shillong, Konkani from Mumbai around the November film festival), skipping the months already published, for `./publish.sh regional/ne` and the like: one split per language in the dataset's `regional` config.

`card.py` writes the dataset card from `card/template.md` and every packaged month; `upload.py` sends one month and the card in one commit. Both name this project's dataset; change `REPO` in `upload.py` to publish your own. The crawl passes, with their office and language codes, are in `passes.tsv`.

## What the fetcher leaves out

- **Embedded posts.** A tweet or an Instagram post inside a release is third-party material, and on translated pages most were left in English. They are removed, known by their tag or, where an editor dropped it, by their link. A tweet pasted as plain paragraphs cannot be told from prose and stays.
- **Contact details.** Email addresses (also "[at]"/"[dot]" forms) become `<email>` and phone numbers in any script `<phone>`, the same on every side of a release, so the sentence and its pair survive.
- **What is not a release.** PIB's error page, withdrawn releases with no text, the visitor counter, and the paragraph every film-festival release repeats.

## Run it on a GPU

`uv run` installs PyPI's PyTorch, which on an AMD GPU runs on the CPU. Make a ROCm environment once and run the aligner with its Python:

```sh
uv venv .venv-rocm
uv pip install -p .venv-rocm torch --index-url https://download.pytorch.org/whl/rocm7.2
uv pip install -p .venv-rocm sentence-transformers numpy
.venv-rocm/bin/python align.py data/2025-11/*/pairs.jsonl > data/2025-11/sentences.jsonl
```

The aligner names the device it runs on. On a GPU it embeds in half precision; its vectors are cached under their own key and give the same pairs as full precision, similarities within 0.001.

## Using PIB's text

PIB's [Copyright Policy](https://www.pib.gov.in/content/3604_2_CopyrightPolicy.aspx), read on 2026-10-04:

> Material featured on this website may be reproduced free of charge and there is no need for any prior approval for using the content. The permission to reproduce this material shall not extend to any third-party material. Authorisation to reproduce such material must be obtained from the departments/copyright holders concerned. The material must be reproduced accurately and not used in a derogatory manner or in a misleading context. Wherever the material is being published or issued to others, the source must be prominently acknowledged.

So: credit PIB, leave the posts out (the fetcher does), and do not present a machine translation as a human one, since some of PIB's translations are near copies of Google Translate.

## Tests

```sh
bun test
uv run --no-project --with pytest --with numpy --with pyyaml pytest -p no:cacheprovider test/
```

The expected outputs come from real pages: the film-festival layout whose style sheet the parser once read as text, the email forms an audit of the published month found after the first rules.

## Licence

The code is MIT. The published dataset: PIB's text under PIB's terms, our annotations (alignment, flags) under CC BY 4.0.
