#!/usr/bin/env bash
# Fetch one month from every PIB office that publishes in its own language.
#
#   ./crawl.sh 2025-11            writes data/2025-11/<office>/{releases,pairs}.jsonl
#
# Delhi's English releases are fetched with every translation they link; each
# regional office's own releases with their English. A document pair found from
# both sides is aligned once (align.py). All passes share one page cache,
# data/html, so a rerun or a crash costs nothing. The passes are passes.tsv;
# office and language codes, offices.tsv. Pages are fetched one at a time, PIB_DELAY ms apart (default 1500).
set -u
month=${1:?usage: ./crawl.sh YYYY-MM}
cd "$(dirname "$0")"
mkdir -p data/html
grep -v '^#' passes.tsv | while IFS=$'\t' read -r name reg lang cols; do
  d=data/$month/$name; mkdir -p "$d"; ln -sfn ../../html "$d/html"
  echo "== $name $(date +%T)"
  PIB_DIR=$d bun fetch.ts --month "$month" --reg "$reg" --lang "$lang" --columns "$cols" < /dev/null > "$d/run.log" 2>&1
  echo "   exit $? | $(grep -h 'releases link' "$d/run.log") | $(tail -1 "$d/run.log")"
done
echo "== done $(date +%T)"
