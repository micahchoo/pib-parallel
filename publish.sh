#!/usr/bin/env bash
# One crawled month to the published dataset: rebuild from the page cache with the
# current parser, align, measure the Google copies, package, audit, card, upload.
# Stops at the first failure; a failed audit stops the upload.
#
#   ./publish.sh 2019-07
set -euo pipefail
month=${1:?usage: ./publish.sh YYYY-MM}
cd "$(dirname "$0")"
PY=${PIB_PYTHON:-}   # a Python with GPU PyTorch for align.py (README: "Run it on a GPU"); uv run otherwise
d=data/$month
echo "== rebuild $(date +%T)"
grep -v '^#' passes.tsv | while IFS=$'\t' read -r name reg lang cols; do
  [ -d "$d/$name" ] || continue
  PIB_DIR=$d/$name PIB_DELAY=500 bun fetch.ts --month "$month" --reg "$reg" --lang "$lang" --columns "$cols" > "$d/$name/rebuild.log" 2>&1
done
echo "== align $(date +%T)"
files=$(ls $d/*/pairs.jsonl | grep -v /bench/)
if [ -n "$PY" ]; then $PY align.py $files > $d/sentences.jsonl 2> $d/align.log; else uv run -q align.py $files > $d/sentences.jsonl 2> $d/align.log; fi
echo "== copies $(date +%T)"
bun copies.ts $d/sentences.jsonl 100 > $d/copies.log 2>&1
echo "== package $(date +%T)"
uv run -q package.py $d
echo "== audit $(date +%T)"
uv run -q audit.py $d
echo "== card and upload $(date +%T)"
uv run -q card.py data > data/hf/README.md
uv run -q upload.py data "$month"
echo "== published $month $(date +%T)"
