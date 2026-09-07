#!/usr/bin/env bash
#SBATCH --job-name=cupid_gl_ddp_smoke
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=200G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_gl_ddp_smoke_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:-/public/home/ricky/CODE/Cupid}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:-/public/home/ricky/RESULTS/CUPID_REPRO_GL_DDP_SMOKE_V1}"
CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312}"

mkdir -p /tmp/ricky_lib "$CUPID_OUTPUT_DIR"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
export LD_LIBRARY_PATH="/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
export no_proxy="${no_proxy:+$no_proxy,}github.com,raw.githubusercontent.com,codeload.github.com,objects.githubusercontent.com,dl.fbaipublicfiles.com,pypi.org,files.pythonhosted.org"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export PYTHONPATH="$CUPID_PROJECT_DIR:$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}"
export ATTN_BACKEND="${ATTN_BACKEND:-xformers}"

cd "$CUPID_PROJECT_DIR"
git_commit="$(git rev-parse HEAD)"
echo "HOST=$(hostname)"
echo "COMMIT=$git_commit"
echo "PYTHON=$CUPID_PYTHON"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
"$CUPID_PYTHON" - <<'PY'
import sys

import orjson
import spconv
import tensorboard
import utils3d
import xformers
import xformers.ops as xops

from cupid.representations.mesh.flexicubes.flexicubes import FlexiCubes
from cupid.utils.tensor_checks import check_tensor

assert check_tensor.__module__ == "cupid.utils.tensor_checks"
assert "kaolin" not in sys.modules
assert "warp" not in sys.modules
assert callable(xops.fmha.attn_bias.BlockDiagonalMask.from_seqlens)
print("CUPID_DDP_IMPORT_GATE_PASS=LOCAL_TENSOR_CHECK_NO_KAOLIN_WARP_XFORMERS_ATTN_BIAS_API")
PY

"$CUPID_PYTHON" -u cupid_train.py \
    --config configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-ddp-smoke.json \
    --data_dir /data/group_gao/trellis/HSSD \
    --output_dir "$CUPID_OUTPUT_DIR" \
    --ckpt none \
    --auto_retry 0 \
    --num_gpus 2 \
    --smoke_steps 1 \
    --smoke_max_attempts 16
