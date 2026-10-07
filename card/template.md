---
pretty_name: PIB Parallel
language:
{{languages_yaml}}
license: other
license_name: pib-copyright-policy-and-cc-by-4.0
license_link: https://huggingface.co/datasets/micahchoo/pib-parallel#terms
task_categories:
- translation
multilinguality:
- translation
size_categories:
- {{size}}
source_datasets:
- original
configs:
{{configs}}
---

# PIB Parallel

English sentences beside their official translations into {{languages_count}} Indian languages, from the press releases India's Press Information Bureau (PIB) published, one month to a split: {{total_pairs}} sentence pairs and {{total_docs}} document pairs from {{month_count}} so far, each pair traceable to the two releases it came from.

PIB is the Government of India's press office. It publishes each release in English and links the same release translated by its offices. Earlier PIB corpora (CVIT-PIB, PMIndia) end around 2019; this one takes whole months, from every office that publishes in its own language, with release IDs. The months are chosen to differ in time, subject and how much of the translation is machine-made. The pipeline that made it, and fetches any other month, is [github.com/micahchoo/pib-parallel](https://github.com/micahchoo/pib-parallel).

Before you use it as a test set, read [How much is machine translation](#how-much-is-machine-translation): part of PIB's translation is a near copy of Google Translate.

## Load it

```python
from datasets import load_dataset

sentences = load_dataset("micahchoo/pib-parallel", "sentences", split="{{first_split}}")
documents = load_dataset("micahchoo/pib-parallel", "documents", split="{{first_split}}")
every_month = load_dataset("micahchoo/pib-parallel", "sentences")  # one split per month
tamil = sentences.filter(lambda r: r["lang"] == "ta" and r["similarity"] >= 0.85)
```

A release is at `https://www.pib.gov.in/PressReleasePage.aspx?PRID=<prid>`.

## What is in it

**`sentences`**: one row per distinct sentence pair.

| Field | Meaning |
| --- | --- |
| `lang` | the translation's language (ISO 639) |
| `en`, `text` | the English sentence and its translation |
| `similarity` | LaBSE cosine similarity of the two, 0.70 or more |
| `numbers_agree` | whether both sides hold the same numbers (lakh, crore, million and billion read as values); null when neither has any |
| `confidence` | `low` for Konkani, Khasi and Manipuri, which LaBSE does not know or knows only through a related language |
| `google_copy` | for a sample of pairs only: whether PIB's text is within chrF 90 of Google Translate's for the same English; null where not checked |
| `occurrences` | how often PIB published this exact pair ("Friends," opens hundreds of speeches) |
| `en_prid`, `text_prid` | the English release and the translated release |
| `office` | the crawl pass that found the pair: `delhi-en` (English releases and every translation they link) or a regional office (its releases and their English) |
| `date`, `posted_by` | the release's date and the office PIB names as its publisher |

**`documents`**: one row per English release and one translation, with both titles and bodies (`en_title`, `en_body`, `title`, `body`), both PRIDs, `ministry`, `office`, `date`, `posted_by`. Use these to align with another aligner, or to work at document level.

## Months

{{months}}

PIB publishes nothing in Bodo, Dogri, Kashmiri, Maithili, Sanskrit, Santali or Sindhi. The offices that publish only their own Hindi (Lucknow, Patna, Bhopal and others) are not crawled.

{{per_month}}

## How it was made

1. **Fetched** from PIB's own pages: every release each office listed for the month, and the translations each release page links. PIB states which releases are translations of which, so no document was matched by guesswork.
2. **Cleaned**: embedded tweets and posts removed (third-party material, and on translated pages most were left in English; 7,908 in November 2025); email addresses and phone numbers replaced by `<email>` and `<phone>` on every side; error pages, withdrawn releases and repeated festival boilerplate dropped.
3. **Aligned**: each release cut into sentences (not after a title such as "Dr." or "डॉ.", or an initial such as "एल."), embedded with [LaBSE](https://huggingface.co/sentence-transformers/LaBSE), and matched in order, one to one, one to two or two to one, by dynamic programming. Pairs below a similarity of 0.70 were dropped. A pair of documents found from both sides was aligned once.
4. **Filtered**: a pair was kept only if each side is mostly in its own script. In November 2025 this dropped 22,673 pairs: links, hashtags, staff initials and English lines left on translated pages, which align because they match themselves; number-only table cells; and Hindi speeches quoted on English pages.
5. **Checked**: every email address and phone number form is searched for again in each month, independently of the rules that removed them, in every script's digits (`audit.py`). A month with any left is not published.

## How much is machine translation

Google Translate translated the English of up to 100 pairs per office and language. A pair whose PIB text is within chrF 90 of Google's counts as a copy. Two independent translations of one sentence almost never come that close: the sarvam-30b model and Google did on 2 of 200 Assamese sentences, and Google and IN22's human translations on 0 of 89 across six languages.

{{copies}}

Samples are 100 pairs unless stated; a blank cell was not measured, or the office linked no translations that month. November 2018 is a sample of ten offices, not a published month. The rate is a lower bound on machine text: a heavily edited Google translation, or another engine, passes as "not a copy". PIB's pages are set up to load Bhashini's machine-translation plugin; text made with it would not show as a copy of Google's. Google today also writes differently from Google years ago, so an older month's rate is a lower bound twice over.

**What this means for a test set.** A score against a Google-made reference favours Google. Use the pairs where `google_copy` is false, or the offices with the lowest rates (Kolkata, Hyderabad, Chennai, Mumbai), or both. `google_copy` is known for {{known}} sampled pairs ({{known_copies}} copies), not for every pair: Google's output itself is not in this dataset, as its terms forbid passing it on.

## Where PIB links its translations

This method needs PIB to link a release to its translation. Ten sampled releases per office, November of each year:

| Office | 2017 | 2018 | 2019 | 2020 to 2024 |
| --- | --- | --- | --- | --- |
| Ahmedabad, Bengaluru, Chennai | 10/10 | 10/10 | 9-10/10 | 10/10 |
| Hyderabad | 7/10 | 10/10 | 10/10 | 10/10 |
| Guwahati, Kolkata, Mumbai, Thiruvananthapuram | 0/10 | 10/10 | 10/10 | 10/10 |
| Chandigarh | 0/10 | 0/10 | 9/10 | 10/10 |
| Bhubaneswar | 0/10 | 0/10 | 0/10 | 10/10 |
| Delhi (English linking any translation) | 0/10 | 5/10 | 8/10 | 10/10 |
| Agartala, Gangtok, Mumbai Konkani, Shillong | no releases until 2023 | | | linked from 2023 |

From 2020 every office links its translations, so the pipeline covers 2020 onward as built. Before that, the regional pages link their English more often than the English pages link their translations, so crawl from the regional side. Releases that link nothing need retrieval, which the pipeline does not do.

## Limits

- **A model can have seen it.** PIB's text is in many training sets.
- **Machine translation in the references**, as measured above.
- **LaBSE's blind spots.** It does not know Manipuri or Khasi and knows Konkani only through Marathi; their pairs are marked `low`, and Manipuri's are weak (30 of 330 at 0.85 or more in November 2025). For every language, a similarity of 0.70 to 0.85 holds more partial and wrong pairs than above 0.85.
- **What the cleaning missed.** Tweets pasted into a release as plain paragraphs, rather than embedded, cannot be told from prose (8 of 10,265 pages in November 2025). A Latin-script translation (Khasi) cannot be told from English by its script, so an English line on a Khasi page can remain.
- **`office`** is the crawl pass that found the pair, not always the office that translated it: Delhi's English releases link translations that regional offices post. `posted_by` names the publisher of the release the pass started from.

## Terms

The text is PIB's. PIB's [Copyright Policy](https://www.pib.gov.in/content/3604_2_CopyrightPolicy.aspx), read on 4 October 2026:

> Material featured on this website may be reproduced free of charge and there is no need for any prior approval for using the content. The permission to reproduce this material shall not extend to any third-party material. Authorisation to reproduce such material must be obtained from the departments/copyright holders concerned. The material must be reproduced accurately and not used in a derogatory manner or in a misleading context. Wherever the material is being published or issued to others, the source must be prominently acknowledged.

So: name PIB as the source, and do not describe these translations as human: some are near copies of Google Translate. Embedded third-party posts were removed for this reason.

The annotations (the sentence alignment, similarities, number and script checks, `google_copy`, `occurrences`) are licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The code is MIT, at [github.com/micahchoo/pib-parallel](https://github.com/micahchoo/pib-parallel).

## Cite

```bibtex
@misc{pib_parallel_2026,
  title        = {{PIB Parallel}: English and Indian languages from the Press Information Bureau},
  author       = {Micah},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/datasets/micahchoo/pib-parallel}},
  note         = {Text: Press Information Bureau, Government of India. Pipeline: \url{https://github.com/micahchoo/pib-parallel}}
}
```
