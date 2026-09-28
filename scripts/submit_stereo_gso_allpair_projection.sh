#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_ALLPAIR_OUTPUT:-/public/home/ricky/RESULTS/STEREO_GSO_ALLPAIR_PROJECTION_V1}"
test ! -e "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=24G --time=02:00:00 \
  --job-name=stereo_gso_allpair_projection \
  --export="ALL,REPO_ROOT=$REPO_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT,OUTPUT_ROOT=$OUTPUT_ROOT" \
  --output="$OUTPUT_ROOT/slurm-%j.out" --error="$OUTPUT_ROOT/slurm-%j.err" \
  "$REPO_ROOT/scripts/stereo_gso_allpair_projection.sbatch"
