#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_INCREMENT_TARGETS_OUTPUT:-/public/home/ricky/RESULTS/STEREO_GSO_1K_INCREMENT_TARGETS_V1}"
SHARD_COUNT="${STEREO_GSO_INCREMENT_SHARD_COUNT:-8}"
MAX_CONCURRENT="${STEREO_GSO_INCREMENT_MAX_CONCURRENT:-4}"
SELECTION_JOB_ID="${STEREO_GSO_SELECTION_JOB_ID:?Set exact 1K selection job ID}"
test "$SHARD_COUNT" -ge 1
test "$MAX_CONCURRENT" -ge 1
test ! -e "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=32G --time=01:00:00 \
  --array="0-$((SHARD_COUNT-1))%$MAX_CONCURRENT" --job-name=stereo_gso_1k_targets \
  --dependency="afterok:$SELECTION_JOB_ID" \
  --export="ALL,REPO_ROOT=$REPO_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT,OUTPUT_ROOT=$OUTPUT_ROOT,SHARD_COUNT=$SHARD_COUNT" \
  --output="$OUTPUT_ROOT/slurm-%A_%a.out" --error="$OUTPUT_ROOT/slurm-%A_%a.err" \
  "$REPO_ROOT/scripts/stereo_gso_1k_increment_targets.sbatch"
