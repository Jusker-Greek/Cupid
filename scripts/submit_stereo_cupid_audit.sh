#!/usr/bin/env bash
#SBATCH --job-name=stereo_cupid_audit
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_cupid_audit_%j.out
set -euo pipefail
: "${SLURM_JOB_ID:?Slurm required}"
: "${CUPID_PROJECT_DIR:?}"
: "${CUPID_EXPECTED_COMMIT:?}"
: "${CUPID_OUTPUT_DIR:?}"
cd "$CUPID_PROJECT_DIR"
test "$(git rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
test -z "$(git status --porcelain)"
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 ATTN_BACKEND=xformers SPCONV_ALGO=native
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$CUPID_PROJECT_DIR:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" -u scripts/inspect_stereo_gso.py --output "$CUPID_OUTPUT_DIR"
"$runtime/bin/python3" -m unittest discover -s tests -p 'test_stereo_*.py' -v
