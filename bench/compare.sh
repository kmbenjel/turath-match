#!/usr/bin/env bash
# Reproduce every number in the README's comparison section. Heavy: run it on a server, not a laptop.
#   bash bench/compare.sh                    # OpenITI benchmarks + OpenRefine head-to-head (public data only)
#   SHAMELA=~/.local/share/shamela bash bench/compare.sh   # + the Shamela edition benchmark on your own install
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
OR_VERSION=${OR_VERSION:-3.10.1}
mkdir -p bench/data bench/out

[ -s bench/data/openiti.tsv ] || $PY -m turath_match.cli fetch openiti -o bench/data/openiti.tsv
[ -s bench/data/book_relations.json ] || curl -sSL -A "turath-match bench" -o bench/data/book_relations.json \
  "https://raw.githubusercontent.com/OpenITI/kitab-metadata-automation/master/output/_home_admin-kitab_Documents_OpenITI_RELEASE_git_working_dir_OpenITI_data_2025-1-9_zenodo+Noor_book_relations.json"

echo "== turath-match on OpenITI (work level)"
$PY bench/openiti_works.py bench/data/openiti.tsv --relations bench/data/book_relations.json --out bench/out/openiti_works.json

echo "== held out: Wikidata records against OpenITI (labelled by the Shamela id both carry)"
$PY bench/wikidata_heldout.py bench/data/openiti.tsv --out bench/out/wikidata_heldout.json

echo "== baseline: exact title equality on the same records (no OpenRefine needed)"
$PY bench/openrefine_compare.py bench/data/openiti.tsv --baseline-only --out bench/out/exact_title_baseline.json

echo "== OpenRefine $OR_VERSION on the same records"
if [ ! -x "bench/data/openrefine-$OR_VERSION/refine" ]; then
  curl -sSL -o bench/data/openrefine.tar.gz \
    "https://github.com/OpenRefine/OpenRefine/releases/download/$OR_VERSION/openrefine-linux-$OR_VERSION.tar.gz"
  tar -xzf bench/data/openrefine.tar.gz -C bench/data
fi
WORK=$(mktemp -d)
REFINE_MEMORY=${REFINE_MEMORY:-8G} "bench/data/openrefine-$OR_VERSION/refine" -i 127.0.0.1 -p 3333 -d "$WORK" -x refine.headless=true \
  > bench/out/openrefine.log 2>&1 &
OR_PID=$!
trap 'kill $OR_PID 2>/dev/null || true; rm -rf "$WORK"' EXIT
for _ in $(seq 120); do curl -s http://127.0.0.1:3333/command/core/get-csrf-token >/dev/null && break; sleep 1; done
$PY bench/openrefine_compare.py bench/data/openiti.tsv --url http://127.0.0.1:3333 --out bench/out/openrefine_compare.json

echo "== 500-book library: time and share decided"
$PY bench/library500.py bench/data/openiti.tsv --out bench/out/library500.json

if [ -n "${SHAMELA:-}" ]; then
  echo "== OpenITI against your Shamela (work + edition level)"
  [ -s bench/data/shamela-cards.jsonl ] || $PY -m turath_match.cli shamela-cards --path "$SHAMELA" -o bench/data/shamela-cards.jsonl
  $PY bench/shamela_openiti.py bench/data/openiti.tsv "$SHAMELA" bench/data/shamela-cards.jsonl --out bench/out/shamela_openiti.json
fi
