#!/usr/bin/env bash
#SBATCH --job-name=cupid_env_setup
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_env_setup_%j.out

set -euo pipefail

CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312}"
CUPID_DINOV2_COMMIT="${CUPID_DINOV2_COMMIT:-7764ea0f912e53c92e82eb78a2a1631e92725fc8}"
CUPID_DINOV2_CHECKPOINT_SIZE="${CUPID_DINOV2_CHECKPOINT_SIZE:-1217607321}"

mkdir -p /tmp/ricky_lib "$CUPID_PYTHON_OVERLAY"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
export LD_LIBRARY_PATH="/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export no_proxy="${CUPID_NO_PROXY:-localhost,127.0.0.1,codeload.github.com,dl.fbaipublicfiles.com}"
export NO_PROXY="$no_proxy"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export CUPID_DINOV2_REPO="facebookresearch/dinov2:$CUPID_DINOV2_COMMIT"

if [[ "${CUPID_SKIP_DEPENDENCY_INSTALL:-0}" != "1" ]]; then
    "$CUPID_PYTHON" -m pip install \
        --upgrade \
        --target "$CUPID_PYTHON_OVERLAY" \
        "numpy==2.0.2" \
        "spconv-cu118==2.3.8" \
        "omegaconf>=2.3,<3"

    "$CUPID_PYTHON" -m pip install \
        --upgrade \
        --no-deps \
        --target "$CUPID_PYTHON_OVERLAY" \
        "https://codeload.github.com/EasternJournalist/utils3d/zip/9a4eb15e4021b67b12c460c7057d642626897ec8"
else
    echo "CUPID_DEPENDENCY_INSTALL_SKIPPED"
fi

PYTHONPATH="$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}" \
    "$CUPID_PYTHON" -c "import spconv, utils3d; print('CUPID_ENV_READY')"

dinov2_repo_dir="$TORCH_HOME/hub/facebookresearch_dinov2_$CUPID_DINOV2_COMMIT"
dinov2_checkpoint="$TORCH_HOME/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth"
mkdir -p "$TORCH_HOME/hub/checkpoints"

if [[ ! -d "$dinov2_repo_dir" ]]; then
    dinov2_tmp_dir="$(mktemp -d "$TORCH_HOME/hub/.dinov2_repo.XXXXXX")"
    curl -fsSL --retry 5 --retry-all-errors \
        "https://codeload.github.com/facebookresearch/dinov2/zip/$CUPID_DINOV2_COMMIT" \
        -o "$dinov2_tmp_dir/dinov2.zip"
    "$CUPID_PYTHON" -m zipfile -e "$dinov2_tmp_dir/dinov2.zip" "$dinov2_tmp_dir/extracted"
    test -f "$dinov2_tmp_dir/extracted/dinov2-$CUPID_DINOV2_COMMIT/hubconf.py"
    mv "$dinov2_tmp_dir/extracted/dinov2-$CUPID_DINOV2_COMMIT" "$dinov2_repo_dir"
    rm -rf "$dinov2_tmp_dir"
fi

if [[ ! -f "$dinov2_checkpoint" ]]; then
    dinov2_checkpoint_tmp="$(mktemp "$TORCH_HOME/hub/checkpoints/.dinov2_vitl14_reg4.XXXXXX")"
    curl -fsSL --retry 5 --retry-all-errors \
        "https://dl.fbaipublicfiles.com/dinov2/dinov2_vitl14/dinov2_vitl14_reg4_pretrain.pth" \
        -o "$dinov2_checkpoint_tmp"
    test "$(stat -c '%s' "$dinov2_checkpoint_tmp")" = "$CUPID_DINOV2_CHECKPOINT_SIZE"
    mv "$dinov2_checkpoint_tmp" "$dinov2_checkpoint"
fi

test -f "$dinov2_repo_dir/hubconf.py"
test "$(stat -c '%s' "$dinov2_checkpoint")" = "$CUPID_DINOV2_CHECKPOINT_SIZE"
dinov2_checkpoint_sha256="$(sha256sum "$dinov2_checkpoint" | awk '{print $1}')"

PYTHONPATH="$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}" \
    "$CUPID_PYTHON" -c "import os, torch; torch.hub.load(os.environ['CUPID_DINOV2_REPO'], 'dinov2_vitl14_reg', pretrained=True, trust_repo=True, skip_validation=True); print('CUPID_DINOV2_MODEL_LOAD_READY')"
echo "CUPID_DINOV2_READY commit=$CUPID_DINOV2_COMMIT checkpoint_sha256=$dinov2_checkpoint_sha256"
