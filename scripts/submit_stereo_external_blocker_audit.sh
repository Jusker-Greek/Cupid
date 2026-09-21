#!/bin/bash
#SBATCH --job-name=stereo_ext_blocker
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_ext_blocker_%j.out
set -euo pipefail
: "${CUPID_PROJECT_DIR:?Set the exact synced checkout}"
: "${CUPID_EXPECTED_COMMIT:?Set the exact expected commit}"
: "${CUPID_OUTPUT_DIR:?Set a fresh output directory}"
cd "$CUPID_PROJECT_DIR"
test "$(git rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
test "$(git status --porcelain)" = ""
python scripts/stereo_external_blocker_audit.py \
  --output "$CUPID_OUTPUT_DIR" \
  --root /public/home/ricky/CODE/GSO_dataset \
  --root /public/home/ricky/DATASET/Gazebo \
  --root /public/home/ricky/DATASET/GSO_1K_200 \
  --max-depth "${CUPID_AUDIT_MAX_DEPTH:-6}"
