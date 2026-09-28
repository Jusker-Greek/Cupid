#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_INCREMENT_OUTPUT:-/public/home/ricky/RESULTS/STEREO_GSO_1K_INCREMENT_V1}"
REPLACEMENT_JOB_ID="${STEREO_GSO_REPLACEMENT_JOB_ID:?Set exact replacement audit job ID}"
test ! -e "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=8G --time=00:15:00 \
  --dependency="afterok:$REPLACEMENT_JOB_ID" --job-name=stereo_gso_1k_selection \
  --export="ALL,REPO_ROOT=$REPO_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT,OUTPUT_ROOT=$OUTPUT_ROOT" \
  --output="$OUTPUT_ROOT/selection-%j.out" --error="$OUTPUT_ROOT/selection-%j.err" \
  "$REPO_ROOT/scripts/stereo_gso_prepare_1k_increment.sbatch"
