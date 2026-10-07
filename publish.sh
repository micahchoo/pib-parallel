#!/usr/bin/env bash
# One crawled month to the published dataset: rebuild from the page cache with the
# current parser, align, measure the Google copies, package, audit, card, upload.
# Stops at the first failure; a failed audit stops the upload.
#
#   ./publish.sh 2019-07         a month split
#   ./publish.sh regional/ne     a regional language, its months pooled
set -euo pipefail
target=${1:?usage: ./publish.sh YYYY-MM | regional/<lang>}
cd "$(dirname "$0")"
PY=${PIB_PYTHON:-}   # a Python with GPU PyTorch for align.py (README: "Run it on a GPU"); uv run otherwise
d=data/$target
files=$(find -H "$d" -name pairs.jsonl -not -path "*/bench/*" -not -path "*/release/*" | sort)
echo "== rebuild $(date +%T)"
for f in $files; do
  pass=$(dirname "$f"); name=$(basename "$pass")
  # A month's passes sit in it; a regional language's sit in its months.
  if [[ $target == regional/* ]]; then month=$(basename "$(dirname "$pass")"); else month=$target; fi
  IFS=$'\t' read -r _ reg lang cols < <(grep -P "^$name\t" passes.tsv)
  # The release list from the crawl: a rebuild asks PIB for nothing.
  PIB_DIR=$pass PIB_DELAY=500 PIB_REUSE_LIST=1 bun fetch.ts --month "$month" --reg "$reg" --lang "$lang" --columns "$cols" < /dev/null > "$pass/rebuild.log" 2>&1
done
echo "== laser $(date +%T)"
uv run -q -p 3.10 laser.py $files 2> $d/laser.log
echo "== align $(date +%T)"
if [ -n "$PY" ]; then $PY align.py $files > $d/sentences.jsonl 2> $d/align.log; else uv run -q align.py $files > $d/sentences.jsonl 2> $d/align.log; fi
echo "== copies $(date +%T)"
bun copies.ts $d/sentences.jsonl 100 > $d/copies.log 2>&1
echo "== package $(date +%T)"
uv run -q package.py $d
echo "== audit $(date +%T)"
uv run -q audit.py $d
echo "== card and upload $(date +%T)"
uv run -q card.py data > data/hf/README.md
uv run -q upload.py data "$target"
echo "== published $target $(date +%T)"
