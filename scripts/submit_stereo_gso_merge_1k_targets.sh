#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_1K_MERGE_OUTPUT:-/public/home/ricky/RESULTS/STEREO_GSO_REPLACED_1K_TARGET_MERGE_V1}"
INCREMENT_ARRAY_JOB_ID="${STEREO_GSO_INCREMENT_ARRAY_JOB_ID:?Set exact increment array job ID}"
test ! -e "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=24G --time=01:00:00 \
  --dependency="afterok:$INCREMENT_ARRAY_JOB_ID" --job-name=stereo_gso_1k_merge \
  --export="ALL,REPO_ROOT=$REPO_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT,OUTPUT_ROOT=$OUTPUT_ROOT" \
  --output="$OUTPUT_ROOT/merge-%j.out" --error="$OUTPUT_ROOT/merge-%j.err" \
  "$REPO_ROOT/scripts/stereo_gso_merge_1k_targets.sbatch"
