#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_TARGET_SHARDS_OUTPUT:?Set exact existing target shard root}"
MERGE_JOB_ID="${STEREO_GSO_MERGE_JOB_ID:?Set exact merge job ID}"
EXPECTED_PAIRS="${STEREO_GSO_EXPECTED_PAIRS:-816}"
test -d "$OUTPUT_ROOT"
test ! -e "$OUTPUT_ROOT/adapter_preflight_receipt.json"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G --time=00:30:00 \
  --dependency="afterok:$MERGE_JOB_ID" --job-name=stereo_gso_adapter \
  --export="ALL,REPO_ROOT=$REPO_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT,OUTPUT_ROOT=$OUTPUT_ROOT,EXPECTED_PAIRS=$EXPECTED_PAIRS" \
  --output="$OUTPUT_ROOT/adapter-%j.out" --error="$OUTPUT_ROOT/adapter-%j.err" \
  "$REPO_ROOT/scripts/stereo_gso_merged_adapter_preflight.sbatch"
