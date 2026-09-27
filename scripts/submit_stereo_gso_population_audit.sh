#!/bin/bash
#SBATCH --job-name=stereo_gso_population
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_gso_population_%j.out
set -euo pipefail
: "${CUPID_PROJECT_DIR:?Set exact synced checkout}"
: "${CUPID_EXPECTED_COMMIT:?Set expected commit}"
: "${CUPID_OUTPUT_DIR:?Set fresh output directory}"
cd "$CUPID_PROJECT_DIR"
test "$(git rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
test "$(git status --porcelain)" = ""
python3 scripts/stereo_gso_population_audit.py \
  --root /public/home/ricky/DATASET/GSO_1K_200 \
  --mesh-root /public/home/ricky/DATASET/Gazebo \
  --output "$CUPID_OUTPUT_DIR" \
  --sample-objects 64
