#!/usr/bin/env bash
#SBATCH --job-name=stereo_cupid_pilot
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_cupid_pilot_%j.out

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch; do not run on login/local host}"
: "${CUPID_PROJECT_DIR:?Existing cluster checkout required}"
: "${CUPID_EXPECTED_COMMIT:?Exact pushed and pulled commit required}"
: "${CUPID_PAIR_DIR:?Existing GSO trajectory with left/right PNGs required}"
: "${CUPID_MODEL_PATH:?Existing hbb1/Cupid pipeline directory required}"
: "${CUPID_DINO_REPO:?Existing local dinov2 repository required}"
: "${CUPID_DINO_CHECKPOINT:?Existing matching DINO checkpoint required}"
: "${CUPID_OUTPUT_DIR:?Fresh output directory required}"

# Reuse the repository's existing runtime paths. No installs or rebuilds.
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
CUPID_NVDIFFRAST_OVERLAY="${CUPID_NVDIFFRAST_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r1}"
CUPID_BASE_PYTHON_OVERLAY="${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}"
CUPID_NVIDIA_PYTHON_ROOT="${CUPID_NVIDIA_PYTHON_ROOT:-/public/home/ricky/.local/lib/python3.12/site-packages/nvidia}"
python_root="$(dirname "$(dirname "$CUPID_PYTHON")")"
runtime_libraries="$python_root/lib:/usr/lib/x86_64-linux-gnu"
if [[ -d /tmp/ricky_lib ]]; then
    runtime_libraries="/tmp/ricky_lib:$runtime_libraries"
fi
for library_dir in "$CUPID_NVIDIA_PYTHON_ROOT"/*/lib; do
    [[ -d "$library_dir" ]] || continue
    runtime_libraries="$library_dir:$runtime_libraries"
done
export LD_LIBRARY_PATH="$runtime_libraries:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$CUPID_PROJECT_DIR:$CUPID_NVDIFFRAST_OVERLAY:$CUPID_BASE_PYTHON_OVERLAY:${PYTHONPATH:-}"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export ATTN_BACKEND="${ATTN_BACKEND:-xformers}"
export SPCONV_ALGO=native HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"

cd "$CUPID_PROJECT_DIR"
[[ "$(git rev-parse HEAD)" == "$CUPID_EXPECTED_COMMIT" ]]
git diff --quiet
git diff --cached --quiet
[[ ! -e "$CUPID_OUTPUT_DIR" ]]
printf 'RUN_CLASS=PRETRAINED_STEREO_PILOT\nCOMMIT=%s\nJOB_ID=%s\n' "$CUPID_EXPECTED_COMMIT" "$SLURM_JOB_ID"

# These are short analytical tests in the same allocated job, not another
# training gate. No dataset, model weights, or fitting to ground truth used.
"$CUPID_PYTHON" -m unittest discover -s tests -p 'test_stereo_*.py' -v

args=(--pair-dir "$CUPID_PAIR_DIR" --frame "${CUPID_FRAME:-000}"
      --model-path "$CUPID_MODEL_PATH" --dino-repo "$CUPID_DINO_REPO"
      --dino-checkpoint "$CUPID_DINO_CHECKPOINT" --output-dir "$CUPID_OUTPUT_DIR"
      --seed "${CUPID_SEED:-42}")
if [[ -n "${CUPID_CAMERA_JSON:-}" ]]; then args+=(--camera-json "$CUPID_CAMERA_JSON"); fi
if [[ "${CUPID_FULL_MESH:-0}" == 1 ]]; then args+=(--full-mesh); fi
if [[ -n "${CUPID_STEPS:-}" ]]; then args+=(--steps "$CUPID_STEPS"); fi
"$CUPID_PYTHON" -u scripts/run_stereo_cupid.py "${args[@]}"
