#!/usr/bin/env bash
#SBATCH --job-name=cupid_gl_smoke
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_gl_smoke_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:-/public/home/ricky/CODE/Cupid}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:-/public/home/ricky/RESULTS/CUPID_REPRO_GL_SMOKE_V1}"
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
if git_commit="$(git rev-parse HEAD 2>/dev/null)"; then
    :
elif [[ -n "${CUPID_COMMIT:-}" ]]; then
    git_commit="$CUPID_COMMIT"
else
    echo "CUPID_COMMIT is required when the checkout has no .git directory" >&2
    exit 2
fi
echo "HOST=$(hostname)"
echo "COMMIT=$git_commit"
echo "PYTHON=$CUPID_PYTHON"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
"$CUPID_PYTHON" -c "import orjson, spconv, tensorboard, utils3d, xformers"

"$CUPID_PYTHON" -u cupid_train.py \
    --config configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-smoke.json \
    --data_dir /data/group_gao/trellis/HSSD \
    --output_dir "$CUPID_OUTPUT_DIR" \
    --ckpt none \
    --auto_retry 0 \
    --num_gpus 1 \
    --smoke_steps 1
