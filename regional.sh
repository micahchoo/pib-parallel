#!/usr/bin/env bash
# Every month of the offices that publish little, for the `regional` config:
# one split per language, its months pooled. Months already published as
# month splits are skipped, so no pair is in both.
#
#   ./regional.sh           writes data/regional/<lang>/<month>/<office>/
#   ./regional.sh --plan    lists what it would fetch
#
# Probed 2026-10-06: Gangtok (Nepali) and Shillong (Khasi) publish steadily
# from 2023; Mumbai publishes Konkani only around IFFI, the November film
# festival in Goa; Mizoram (Mizo) and Kohima (Tenyidei) publish nothing.
set -u
cd "$(dirname "$0")"
published=$(ls -d data/20??-??/release 2>/dev/null | cut -d/ -f2)

months() { # first last, as YYYY-MM
  local y m
  for y in $(seq "${1%-*}" "${2%-*}"); do
    for m in $(seq -w 1 12); do
      [[ "$y-$m" < "$1" || "$y-$m" > "$2" ]] || echo "$y-$m"
    done
  done
}

plan() {
  local m
  for m in $(months 2023-01 2026-09); do echo "ne gangtok-ne $m"; echo "kha shillong-kha $m"; done
  for m in 2023-11 2024-11; do echo "gom mumbai-gom $m"; done
}

todo=$(plan | while read -r lang name month; do echo "$published" | grep -qx "$month" || echo "$lang $name $month"; done)
if [ "${1:-}" = --plan ]; then
  echo "skipped, already month splits: $(echo $published)"
  echo "$todo" | awk '{n[$1]++} END {for (l in n) print l, n[l], "office-months"}'
  exit 0
fi

mkdir -p data/html
echo "$todo" | while read -r lang name month; do
  IFS=$'\t' read -r _ reg feed cols < <(grep -P "^$name\t" passes.tsv)
  d=data/regional/$lang/$month/$name
  mkdir -p "$d"; ln -sfn ../../../../html "$d/html"
  PIB_DIR=$d bun fetch.ts --month "$month" --reg "$reg" --lang "$feed" --columns "$cols" < /dev/null > "$d/run.log" 2>&1
  echo "$lang $month exit $? | $(grep -h 'releases link' "$d/run.log")"
done
echo "== done $(date +%T)"
