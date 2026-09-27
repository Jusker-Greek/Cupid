#!/usr/bin/env bash
# Submit from a fresh GitHub-synced checkout on the cluster login node.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="${STEREO_GSO_1K_D_AUDIT_OUTPUT:-/public/home/ricky/RESULTS/STEREO_GSO_1K_D_CROSS_AUDIT_V1}"
mkdir -p "$OUTPUT_ROOT"
/opt/gridview/slurm/bin/sbatch --parsable \
  --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=32G --time=02:00:00 \
  --job-name=stereo_gso_1k_d_audit \
  --export="ALL,REPO_ROOT=$REPO_ROOT,OUTPUT_ROOT=$OUTPUT_ROOT,EXPECTED_COMMIT=$EXPECTED_COMMIT" \
  --output="$OUTPUT_ROOT/slurm-%j.out" \
  --error="$OUTPUT_ROOT/slurm-%j.err" \
  "$REPO_ROOT/scripts/stereo_gso_1k_cross_audit.sbatch"
