#!/usr/bin/env bash
#SBATCH --job-name=cupid_tb_readback
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_tb_readback_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:?CUPID_PROJECT_DIR is required}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:?CUPID_OUTPUT_DIR is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312}"

export PYTHONPATH="$CUPID_PROJECT_DIR:$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}"
cd "$CUPID_PROJECT_DIR"
echo "HOST=$(hostname)"
echo "COMMIT=$(git rev-parse HEAD)"
"$CUPID_PYTHON" scripts/verify_cupid_tensorboard.py --output_dir "$CUPID_OUTPUT_DIR"
