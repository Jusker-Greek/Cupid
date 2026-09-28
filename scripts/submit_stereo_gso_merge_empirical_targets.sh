#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_TARGET_SHARDS_OUTPUT:?Set exact existing target shard root}"
SHARD_COUNT="${STEREO_GSO_SHARD_COUNT:-8}"
SHARD_COMMIT="${STEREO_GSO_SHARD_COMMIT:?Set exact shard code commit}"
ARRAY_JOB_ID="${STEREO_GSO_ARRAY_JOB_ID:?Set exact array job ID}"
test -d "$OUTPUT_ROOT"
test ! -e "$OUTPUT_ROOT/merge_receipt.json"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G --time=01:00:00 \
  --dependency="afterok:$ARRAY_JOB_ID" --job-name=stereo_gso_merge \
  --export="ALL,REPO_ROOT=$REPO_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT,OUTPUT_ROOT=$OUTPUT_ROOT,SHARD_COUNT=$SHARD_COUNT,SHARD_COMMIT=$SHARD_COMMIT" \
  --output="$OUTPUT_ROOT/merge-%j.out" --error="$OUTPUT_ROOT/merge-%j.err" \
  "$REPO_ROOT/scripts/stereo_gso_merge_empirical_targets.sbatch"
