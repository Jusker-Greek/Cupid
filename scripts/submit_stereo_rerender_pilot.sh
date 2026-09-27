#!/usr/bin/env bash
# Submit from a fresh GitHub-synced checkout on the cluster login node.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${STEREO_RERENDER_OUTPUT_ROOT:-/public/home/ricky/RESULTS/CUPID_STEREO_RERENDER_PILOT_V1}"
BLENDER="/public/home/ricky/blender/blender-3.6.5-linux-x64/blender"
JOB_SCRIPT="$REPO_ROOT/scripts/stereo_rerender_pilot.sbatch"

mkdir -p "$OUTPUT_ROOT"
sbatch --parsable \
  --export="ALL,REPO_ROOT=$REPO_ROOT,OUTPUT_ROOT=$OUTPUT_ROOT,BLENDER=$BLENDER" \
  --output="$OUTPUT_ROOT/slurm-%j.out" \
  --error="$OUTPUT_ROOT/slurm-%j.err" \
  "$JOB_SCRIPT"
