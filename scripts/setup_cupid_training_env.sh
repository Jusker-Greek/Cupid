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

mkdir -p /tmp/ricky_lib "$CUPID_PYTHON_OVERLAY"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
export LD_LIBRARY_PATH="/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
export no_proxy="${no_proxy:+$no_proxy,}github.com,codeload.github.com,pypi.org,files.pythonhosted.org"

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

PYTHONPATH="$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}" \
    "$CUPID_PYTHON" -c "import spconv, utils3d; print('CUPID_ENV_READY')"
