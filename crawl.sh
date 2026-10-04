#!/usr/bin/env bash
# Fetch one month from every PIB office that publishes in its own language.
#
#   ./crawl.sh 2025-11            writes data/2025-11/<office>/{releases,pairs}.jsonl
#
# Delhi's English releases are fetched with every translation they link; each
# regional office's own releases with their English. A document pair found from
# both sides is aligned once (align.py). All passes share one page cache,
# data/html, so a rerun or a crash costs nothing. Office and language codes:
# offices.tsv. Pages are fetched one at a time, PIB_DELAY ms apart (default 1500).
set -u
month=${1:?usage: ./crawl.sh YYYY-MM}
cd "$(dirname "$0")"
ALL=hi,ur,mr,gom,pa,bn,kn,or,gu,as,ml,mni,ne,ta,te,lus,kha,njm
mkdir -p data/html
for spec in delhi-en:3:1:$ALL mumbai-mr:1:9:en mumbai-gom:1:42:en hyderabad-te:5:16:en chennai-ta:6:11:en \
            chandigarh-pa:17:6:en kolkata-bn:19:4:en bengaluru-kn:20:8:en bhubaneswar-or:21:18:en ahmedabad-gu:22:13:en \
            guwahati-as:23:10:en thiruvananthapuram-ml:24:15:en imphal-mni:30:14:en gangtok-ne:33:29:en \
            shillong-kha:35:30:en agartala-bn:32:37:en mizoram-lus:31:32:en kohima-njm:34:31:en vijayawada-te:45:46:en \
            jk-ur:44:44:en; do
  IFS=: read name reg lang cols <<< "$spec"
  d=data/$month/$name; mkdir -p "$d"; ln -sfn ../../html "$d/html"
  echo "== $name $(date +%T)"
  PIB_DIR=$d bun fetch.ts --month "$month" --reg "$reg" --lang "$lang" --columns "$cols" > "$d/run.log" 2>&1
  echo "   exit $? | $(grep -h 'releases link' "$d/run.log") | $(tail -1 "$d/run.log")"
done
echo "== done $(date +%T)"
