#!/usr/bin/env bash
#SBATCH --job-name=cupid_gl_smoke
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=200G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_gl_smoke_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:?CUPID_PROJECT_DIR is required}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:?CUPID_OUTPUT_DIR is required}"
CUPID_EXPECTED_COMMIT="${CUPID_EXPECTED_COMMIT:?CUPID_EXPECTED_COMMIT is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
CUPID_NVDIFFRAST_OVERLAY="${CUPID_NVDIFFRAST_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v17}"
CUPID_BASE_PYTHON_OVERLAY="${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}"
CUPID_NVIDIA_PYTHON_ROOT="${CUPID_NVIDIA_PYTHON_ROOT:-/public/home/ricky/.local/lib/python3.12/site-packages/nvidia}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-$CUPID_NVDIFFRAST_OVERLAY:$CUPID_BASE_PYTHON_OVERLAY}"

mkdir -p /tmp/ricky_lib "$CUPID_OUTPUT_DIR"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
python_root="$(dirname "$(dirname "$CUPID_PYTHON")")"
test -f "$python_root/lib/libpython3.12.so.1.0"
nvidia_library_path=""
for library_dir in "$CUPID_NVIDIA_PYTHON_ROOT"/*/lib; do
    test -d "$library_dir" || continue
    nvidia_library_path="${nvidia_library_path:+$nvidia_library_path:}$library_dir"
done
test -n "$nvidia_library_path"
export LD_LIBRARY_PATH="$nvidia_library_path:$python_root/lib:/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export PYTHONPATH="$CUPID_PROJECT_DIR:$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}"
export ATTN_BACKEND="${ATTN_BACKEND:-xformers}"

cd "$CUPID_PROJECT_DIR"
git_commit="$(git rev-parse HEAD)"
test "$git_commit" = "$CUPID_EXPECTED_COMMIT"
test -z "$(git status --porcelain --untracked-files=all)"
echo "HOST=$(hostname)"
echo "COMMIT=$git_commit"
echo "PYTHON_OVERLAY=$CUPID_PYTHON_OVERLAY"
echo "NUM_GPUS=1"
echo "RUN_CLASS=SMOKE_DEBUG"
echo "EVIDENCE_ELIGIBILITY=DEBUG_ONLY/NO_SCIENCE"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
"$CUPID_PYTHON" - <<'PY'
import spconv
import tensorboard
import utils3d
import xformers
import nvdiffrast.torch

print("CUPID_SINGLE_GPU_IMPORT_GATE=PASS")
PY

"$CUPID_PYTHON" -u cupid_train.py \
    --config configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-smoke.json \
    --data_dir /data/group_gao/trellis/HSSD \
    --output_dir "$CUPID_OUTPUT_DIR" \
    --ckpt none \
    --auto_retry 0 \
    --num_gpus 1 \
    --smoke_full_entry \
    --smoke_steps 1 \
    --smoke_max_attempts 16
