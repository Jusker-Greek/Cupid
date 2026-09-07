#!/usr/bin/env bash
#SBATCH --job-name=cupid_nvdiffrast_build
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_nvdiffrast_build_%j.out

set -euo pipefail

CUPID_NVDIFFRAST_OVERLAY="${CUPID_NVDIFFRAST_OVERLAY:?CUPID_NVDIFFRAST_OVERLAY is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
CUPID_BASE_PYTHON_OVERLAY="${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}"
NVDIFFRAST_COMMIT="${NVDIFFRAST_COMMIT:-253ac4fcea7de5f396371124af597e6cc957bfae}"
NVDIFFRAST_ARCHIVE_SHA256="${NVDIFFRAST_ARCHIVE_SHA256:-b79ea0237cad81db8e1fc15839eb50b47ec2bfc8ae6cdcd21ef77a05ea778042}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname "$script_dir")"
source_archive="$project_dir/third_party/nvdiffrast-${NVDIFFRAST_COMMIT}.tar.gz"

test ! -e "$CUPID_NVDIFFRAST_OVERLAY"
mkdir -p "$(dirname "$CUPID_NVDIFFRAST_OVERLAY")"

build_root="$(mktemp -d "${SLURM_TMPDIR:-/tmp}/cupid_nvdiffrast.XXXXXX")"
trap 'rm -rf "$build_root"' EXIT

export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"

test -f "$source_archive"
test "$(sha256sum "$source_archive" | awk '{print $1}')" = "$NVDIFFRAST_ARCHIVE_SHA256"
tar -xzf "$source_archive" -C "$build_root"
source_dir="$build_root/nvdiffrast-253ac4f"
test -f "$source_dir/LICENSE.txt"

mkdir "$CUPID_NVDIFFRAST_OVERLAY"
"$CUPID_PYTHON" -m pip install \
    --target "$CUPID_NVDIFFRAST_OVERLAY" \
    --no-deps \
    --no-cache-dir \
    --no-build-isolation \
    "$source_dir"

export PYTHONPATH="$CUPID_NVDIFFRAST_OVERLAY:$CUPID_BASE_PYTHON_OVERLAY:${PYTHONPATH:-}"
export CUPID_NVDIFFRAST_OVERLAY NVDIFFRAST_COMMIT NVDIFFRAST_ARCHIVE_SHA256
"$CUPID_PYTHON" - <<'PY'
import json
import os
from pathlib import Path

import torch
import nvdiffrast.torch as dr

context = dr.RasterizeCudaContext()
positions = torch.tensor(
    [[[-0.8, -0.8, 0.0, 1.0], [0.8, -0.8, 0.0, 1.0], [0.0, 0.8, 0.0, 1.0]]],
    device="cuda",
    dtype=torch.float32,
)
triangles = torch.tensor([[0, 1, 2]], device="cuda", dtype=torch.int32)
raster, _ = dr.rasterize(context, positions, triangles, resolution=[8, 8])
torch.cuda.synchronize()
if raster.shape != (1, 8, 8, 4) or not torch.isfinite(raster).all():
    raise RuntimeError(f"Unexpected nvdiffrast probe output: {raster.shape}")

receipt = {
    "schema": "cupid_nvdiffrast_overlay/v1",
    "status": "PASS",
    "source": "https://github.com/NVlabs/nvdiffrast.git",
    "commit": os.environ["NVDIFFRAST_COMMIT"],
    "archive_sha256": os.environ["NVDIFFRAST_ARCHIVE_SHA256"],
    "overlay": os.environ["CUPID_NVDIFFRAST_OVERLAY"],
    "torch": torch.__version__,
    "torch_cuda": torch.version.cuda,
    "gpu": torch.cuda.get_device_name(),
    "probe_shape": list(raster.shape),
    "evidence_eligibility": "ENGINEERING_ONLY / NO_SCIENCE",
}
Path(os.environ["CUPID_NVDIFFRAST_OVERLAY"], "overlay_receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n"
)
print("NVDIFFRAST_OVERLAY_RECEIPT=" + json.dumps(receipt, sort_keys=True), flush=True)
PY
