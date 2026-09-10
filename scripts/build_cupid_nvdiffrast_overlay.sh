#!/usr/bin/env bash
#SBATCH --job-name=cupid_nvdiffrast_build
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=200G
#SBATCH --time=00:30:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_nvdiffrast_build_%j.out

set -euo pipefail

echo "NVDIFFRAST_BUILD_STAGE=START host=$(hostname) job=${SLURM_JOB_ID:-NONE}"

CUPID_NVDIFFRAST_OVERLAY="${CUPID_NVDIFFRAST_OVERLAY:?CUPID_NVDIFFRAST_OVERLAY is required}"
CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:?CUPID_PROJECT_DIR is required}"
CUPID_EXPECTED_COMMIT="${CUPID_EXPECTED_COMMIT:?CUPID_EXPECTED_COMMIT is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
CUPID_BASE_PYTHON_OVERLAY="${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}"
CUPID_CUDA_TOOLKIT_DIR="${CUPID_CUDA_TOOLKIT_DIR:-/public/home/ricky/ENVIRONMENT/cupid_cuda_toolkit_11_8_89_v1}"
CUPID_NVIDIA_PYTHON_ROOT="${CUPID_NVIDIA_PYTHON_ROOT:-/public/home/ricky/.local/lib/python3.12/site-packages/nvidia}"
NVDIFFRAST_COMMIT="${NVDIFFRAST_COMMIT:-253ac4fcea7de5f396371124af597e6cc957bfae}"
NVDIFFRAST_ARCHIVE_SHA256="${NVDIFFRAST_ARCHIVE_SHA256:-a57340159afcef86b047f9a92d024b21fd7443c76bb1b5e67ab6ff8b172908ab}"
MIP_SPLATTING_COMMIT="${MIP_SPLATTING_COMMIT:-dda02ab5ecf45d6edb8c540d9bb65c7e451345a9}"
MIP_SPLATTING_ARCHIVE_SHA256="${MIP_SPLATTING_ARCHIVE_SHA256:-3c82ded3bb9fcf8137749fca8be01e50424c74ef3c5c8416a3ca5547aedeefe4}"
SETUPTOOLS_WHEEL_SHA256="${SETUPTOOLS_WHEEL_SHA256:-558e47c15f1811c1fa7adbd0096669bf76c1d3f433f58324df69f3f5ecac4e8f}"
WHEEL_WHEEL_SHA256="${WHEEL_WHEEL_SHA256:-708e7481cc80179af0e556bbf0cc00b8444c7321e2700b8d8580231d13017248}"
TYPING_EXTENSIONS_WHEEL_SHA256="${TYPING_EXTENSIONS_WHEEL_SHA256:-04e5ca0351e0f3f85c6853954072df659d0d13fac324d0072316b67d7794700d}"
PLATFORMDIRS_WHEEL_SHA256="${PLATFORMDIRS_WHEEL_SHA256:-ff7059bb7eb1179e2685604f4aaf157cfd9535242bd23742eadc3c13542139b4}"
PACKAGING_WHEEL_SHA256="${PACKAGING_WHEEL_SHA256:-09abb1bccd265c01f4a3aa3f7a7db064b36514d2cba19a2f694fe6150451a759}"
PANDAS_WHEEL_SHA256="${PANDAS_WHEEL_SHA256:-fffb8ae78d8af97f849404f21411c95062db1496aeb3e56f146f0355c9989319}"
PYTHON_DATEUTIL_WHEEL_SHA256="${PYTHON_DATEUTIL_WHEEL_SHA256:-a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427}"
TZDATA_WHEEL_SHA256="${TZDATA_WHEEL_SHA256:-7e127113816800496f027041c570f50bcd464a020098a3b6b199517772303639}"
SIX_WHEEL_SHA256="${SIX_WHEEL_SHA256:-4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274}"
PILLOW_WHEEL_SHA256="${PILLOW_WHEEL_SHA256:-7fdadc077553621911f27ce206ffcbec7d3f8d7b50e0da39f10997e8e2bb7f6a}"
PROTOBUF_WHEEL_SHA256="${PROTOBUF_WHEEL_SHA256:-0a18ed4a24198528f2333802eb075e59dea9d679ab7a6c5efb017a59004d849f}"
SCIPY_WHEEL_SHA256="${SCIPY_WHEEL_SHA256:-0fb57b30f0017d4afa5fe5f5b150b8f807618819287c21cbe51130de7ccdaed2}"
PYDANTIC_WHEEL_SHA256="${PYDANTIC_WHEEL_SHA256:-427d664bf0b8a2b34ff5dd0f5a18df00591adcee7198fbd71981054cef37b584}"
PYDANTIC_CORE_WHEEL_SHA256="${PYDANTIC_CORE_WHEEL_SHA256:-6fb4aadc0b9a0c063206846d603b92030eb6f03069151a625667f982887153e2}"
ANNOTATED_TYPES_WHEEL_SHA256="${ANNOTATED_TYPES_WHEEL_SHA256:-1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53}"
TYPING_INSPECTION_WHEEL_SHA256="${TYPING_INSPECTION_WHEEL_SHA256:-389055682238f53b04f7badcb49b989835495a96700ced5dab2d8feae4b26f51}"
CUDA_PACKAGE_BASE_URL="${CUDA_PACKAGE_BASE_URL:-https://conda.anaconda.org/nvidia/linux-64}"

test "$(git -C "$CUPID_PROJECT_DIR" rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
test -z "$(git -C "$CUPID_PROJECT_DIR" status --porcelain --untracked-files=all)"
source_archive="$CUPID_PROJECT_DIR/third_party/nvdiffrast-${NVDIFFRAST_COMMIT}.tar.gz"
mip_splatting_archive="$CUPID_PROJECT_DIR/third_party/mip-splatting-${MIP_SPLATTING_COMMIT}.tar.gz"
setuptools_wheel="$CUPID_PROJECT_DIR/third_party/setuptools-75.8.2-py3-none-any.whl"
wheel_wheel="$CUPID_PROJECT_DIR/third_party/wheel-0.45.1-py3-none-any.whl"
typing_extensions_wheel="$CUPID_PROJECT_DIR/third_party/typing_extensions-4.12.2-py3-none-any.whl"
platformdirs_wheel="$CUPID_PROJECT_DIR/third_party/platformdirs-4.3.8-py3-none-any.whl"
packaging_wheel="$CUPID_PROJECT_DIR/third_party/packaging-24.2-py3-none-any.whl"
pandas_wheel="$CUPID_PROJECT_DIR/third_party/pandas-2.2.3-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
python_dateutil_wheel="$CUPID_PROJECT_DIR/third_party/python_dateutil-2.9.0.post0-py2.py3-none-any.whl"
tzdata_wheel="$CUPID_PROJECT_DIR/third_party/tzdata-2025.1-py2.py3-none-any.whl"
six_wheel="$CUPID_PROJECT_DIR/third_party/six-1.17.0-py2.py3-none-any.whl"
pillow_wheel="$CUPID_PROJECT_DIR/third_party/pillow-11.1.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
protobuf_wheel="$CUPID_PROJECT_DIR/third_party/protobuf-5.29.3-py3-none-any.whl"
scipy_wheel="$CUPID_PROJECT_DIR/third_party/scipy-1.15.1-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
pydantic_wheel="$CUPID_PROJECT_DIR/third_party/pydantic-2.10.6-py3-none-any.whl"
pydantic_core_wheel="$CUPID_PROJECT_DIR/third_party/pydantic_core-2.27.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
annotated_types_wheel="$CUPID_PROJECT_DIR/third_party/annotated_types-0.7.0-py3-none-any.whl"
typing_inspection_wheel="$CUPID_PROJECT_DIR/third_party/typing_inspection-0.4.1-py3-none-any.whl"
echo "NVDIFFRAST_BUILD_STAGE=PATHS overlay=$CUPID_NVDIFFRAST_OVERLAY archive=$source_archive"

test ! -e "$CUPID_NVDIFFRAST_OVERLAY"
mkdir -p "$(dirname "$CUPID_NVDIFFRAST_OVERLAY")"
echo "NVDIFFRAST_BUILD_STAGE=TARGET_READY"

build_root="$(mktemp -d /tmp/cupid_nvdiffrast.XXXXXX)"
trap 'rm -rf "$build_root"' EXIT
echo "NVDIFFRAST_BUILD_STAGE=TEMP_READY path=$build_root"

cuda_packages=(
    "cuda-nvcc-11.8.89-0.tar.bz2:23ee509485627c7e402d0d6c4567e02641430a37581f1da0a4d5478dd5cecc0e"
    "cuda-cudart-11.8.89-0.tar.bz2:f8cf96ae45acf1bef5ff0be3e849d87e3543144ec8c0075db235f4933113a3b0"
    "cuda-cudart-dev-11.8.89-0.tar.bz2:46f31a6b45ebdb09e03f3e0ec8a3cba13ceef53805de87de5ab0056b7ff69d80"
    "cuda-cccl-11.8.89-0.tar.bz2:cc68223476b91e15de718d4e31470ac9166e86eb123528bb61ec0b83c2ea1474"
)

verify_cuda_toolkit() {
    test -x "$CUPID_CUDA_TOOLKIT_DIR/bin/nvcc"
    test -f "$CUPID_CUDA_TOOLKIT_DIR/include/cuda_runtime.h"
    test -f "$CUPID_CUDA_TOOLKIT_DIR/lib/libcudart.so.11.8.89"
    "$CUPID_CUDA_TOOLKIT_DIR/bin/nvcc" --version | grep -q 'release 11.8'
}

if ! verify_cuda_toolkit 2>/dev/null; then
    test ! -e "$CUPID_CUDA_TOOLKIT_DIR"
    cuda_partial="${CUPID_CUDA_TOOLKIT_DIR}.partial-${SLURM_JOB_ID:-manual}"
    test ! -e "$cuda_partial"
    mkdir -p "$cuda_partial" "$build_root/cuda_packages"
    echo "NVDIFFRAST_BUILD_STAGE=CUDA_TOOLKIT_DOWNLOAD_START target=$CUPID_CUDA_TOOLKIT_DIR"
    for package_spec in "${cuda_packages[@]}"; do
        package_name="${package_spec%%:*}"
        package_sha256="${package_spec##*:}"
        package_path="$build_root/cuda_packages/$package_name"
        curl --fail --location --retry 3 --retry-all-errors \
            "$CUDA_PACKAGE_BASE_URL/$package_name" --output "$package_path"
        test "$(sha256sum "$package_path" | awk '{print $1}')" = "$package_sha256"
        tar -xjf "$package_path" -C "$cuda_partial"
    done
    ln -s lib "$cuda_partial/lib64"
    test -x "$cuda_partial/bin/nvcc"
    test -f "$cuda_partial/include/cuda_runtime.h"
    test -f "$cuda_partial/lib/libcudart.so.11.8.89"
    "$cuda_partial/bin/nvcc" --version | grep -q 'release 11.8'
    mv "$cuda_partial" "$CUPID_CUDA_TOOLKIT_DIR"
fi
verify_cuda_toolkit
export CUDA_HOME="$CUPID_CUDA_TOOLKIT_DIR"
export PATH="$CUDA_HOME/bin:$PATH"
echo "NVDIFFRAST_BUILD_STAGE=CUDA_TOOLKIT_READY path=$CUDA_HOME version=$(nvcc --version | grep release | xargs)"

# CUDA 11.8 ptxas exhausts node memory on nvdiffrast's native sm90 raster kernel.
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.0+PTX}"
echo "NVDIFFRAST_BUILD_STAGE=CUDA_ARCH_READY arch=$TORCH_CUDA_ARCH_LIST"

nvidia_include_path=""
nvidia_library_path=""
for include_dir in "$CUPID_NVIDIA_PYTHON_ROOT"/*/include; do
    test -d "$include_dir" || continue
    nvidia_include_path="${nvidia_include_path:+$nvidia_include_path:}$include_dir"
done
for library_dir in "$CUPID_NVIDIA_PYTHON_ROOT"/*/lib; do
    test -d "$library_dir" || continue
    nvidia_library_path="${nvidia_library_path:+$nvidia_library_path:}$library_dir"
done
test -n "$nvidia_include_path"
test -n "$nvidia_library_path"
test -f "$CUPID_NVIDIA_PYTHON_ROOT/cusparse/include/cusparse.h"
test -f "$CUPID_NVIDIA_PYTHON_ROOT/cusparse/lib/libcusparse.so.11"
export CPATH="$nvidia_include_path:${CPATH:-}"
export LIBRARY_PATH="$nvidia_library_path:${LIBRARY_PATH:-}"
echo "NVDIFFRAST_BUILD_STAGE=CUDA_DEPENDENCY_PATHS_READY root=$CUPID_NVIDIA_PYTHON_ROOT"

mkdir -p /tmp/ricky_lib
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
python_root="$(dirname "$(dirname "$CUPID_PYTHON")")"
test -f "$python_root/lib/libpython3.12.so.1.0"
export LD_LIBRARY_PATH="$nvidia_library_path:$CUDA_HOME/lib:$python_root/lib:/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONNOUSERSITE=1
bootstrap_pythonpath="$CUPID_BASE_PYTHON_OVERLAY:/public/home/ricky/.local/lib/python3.12/site-packages:${PYTHONPATH:-}"
build_backend="$build_root/build_backend"
test "$(sha256sum "$setuptools_wheel" | awk '{print $1}')" = "$SETUPTOOLS_WHEEL_SHA256"
test "$(sha256sum "$wheel_wheel" | awk '{print $1}')" = "$WHEEL_WHEEL_SHA256"
test "$(sha256sum "$typing_extensions_wheel" | awk '{print $1}')" = "$TYPING_EXTENSIONS_WHEEL_SHA256"
test "$(sha256sum "$platformdirs_wheel" | awk '{print $1}')" = "$PLATFORMDIRS_WHEEL_SHA256"
test "$(sha256sum "$packaging_wheel" | awk '{print $1}')" = "$PACKAGING_WHEEL_SHA256"
test "$(sha256sum "$pandas_wheel" | awk '{print $1}')" = "$PANDAS_WHEEL_SHA256"
test "$(sha256sum "$python_dateutil_wheel" | awk '{print $1}')" = "$PYTHON_DATEUTIL_WHEEL_SHA256"
test "$(sha256sum "$tzdata_wheel" | awk '{print $1}')" = "$TZDATA_WHEEL_SHA256"
test "$(sha256sum "$six_wheel" | awk '{print $1}')" = "$SIX_WHEEL_SHA256"
test "$(sha256sum "$pillow_wheel" | awk '{print $1}')" = "$PILLOW_WHEEL_SHA256"
test "$(sha256sum "$protobuf_wheel" | awk '{print $1}')" = "$PROTOBUF_WHEEL_SHA256"
test "$(sha256sum "$scipy_wheel" | awk '{print $1}')" = "$SCIPY_WHEEL_SHA256"
test "$(sha256sum "$pydantic_wheel" | awk '{print $1}')" = "$PYDANTIC_WHEEL_SHA256"
test "$(sha256sum "$pydantic_core_wheel" | awk '{print $1}')" = "$PYDANTIC_CORE_WHEEL_SHA256"
test "$(sha256sum "$annotated_types_wheel" | awk '{print $1}')" = "$ANNOTATED_TYPES_WHEEL_SHA256"
test "$(sha256sum "$typing_inspection_wheel" | awk '{print $1}')" = "$TYPING_INSPECTION_WHEEL_SHA256"
PYTHONPATH="$bootstrap_pythonpath" "$CUPID_PYTHON" -m pip install \
    --target "$build_backend" --no-deps --no-index \
    "$setuptools_wheel" "$wheel_wheel" "$typing_extensions_wheel"
export PYTHONPATH="$build_backend:$bootstrap_pythonpath"
"$CUPID_PYTHON" -c 'import setuptools, setuptools.build_meta, torch; print(f"NVDIFFRAST_BUILD_BACKEND=setuptools:{setuptools.__version__}|torch:{torch.__version__}|cuda:{torch.version.cuda}")'
echo "NVDIFFRAST_BUILD_STAGE=PYTHON_READY path=$CUPID_PYTHON lib=$python_root/lib"

test -f "$source_archive"
test "$(sha256sum "$source_archive" | awk '{print $1}')" = "$NVDIFFRAST_ARCHIVE_SHA256"
test -f "$mip_splatting_archive"
test "$(sha256sum "$mip_splatting_archive" | awk '{print $1}')" = "$MIP_SPLATTING_ARCHIVE_SHA256"
echo "NVDIFFRAST_BUILD_STAGE=ARCHIVE_VERIFIED sha256=$NVDIFFRAST_ARCHIVE_SHA256"
tar -xzf "$source_archive" -C "$build_root"
source_dir="$build_root/nvdiffrast-253ac4f"
test -f "$source_dir/LICENSE.txt"
tar -xzf "$mip_splatting_archive" -C "$build_root"
gaussian_source_dir="$build_root/mip-splatting-${MIP_SPLATTING_COMMIT}/submodules/diff-gaussian-rasterization"
test -f "$gaussian_source_dir/setup.py"
echo "NVDIFFRAST_BUILD_STAGE=SOURCE_EXTRACTED path=$source_dir"

mkdir "$CUPID_NVDIFFRAST_OVERLAY"
echo "NVDIFFRAST_BUILD_STAGE=PIP_INSTALL_START"
"$CUPID_PYTHON" -m pip install \
    --target "$CUPID_NVDIFFRAST_OVERLAY" \
    --no-deps \
    --no-cache-dir \
    --no-build-isolation \
    "$source_dir"
"$CUPID_PYTHON" -m pip install \
    --target "$CUPID_NVDIFFRAST_OVERLAY" \
    --no-deps \
    --no-index \
    "$typing_extensions_wheel" "$platformdirs_wheel" "$packaging_wheel" \
    "$pandas_wheel" "$python_dateutil_wheel" "$tzdata_wheel" "$six_wheel" "$pillow_wheel" \
    "$protobuf_wheel" "$scipy_wheel" \
    "$pydantic_wheel" "$pydantic_core_wheel" "$annotated_types_wheel" "$typing_inspection_wheel"
MAX_JOBS="${MAX_JOBS:-4}" "$CUPID_PYTHON" -m pip install \
    --target "$CUPID_NVDIFFRAST_OVERLAY" \
    --no-deps \
    --no-cache-dir \
    --no-build-isolation \
    "$gaussian_source_dir"
echo "NVDIFFRAST_BUILD_STAGE=PIP_INSTALL_DONE"

export PYTHONPATH="$CUPID_NVDIFFRAST_OVERLAY:$PYTHONPATH"
export CUPID_NVDIFFRAST_OVERLAY NVDIFFRAST_COMMIT NVDIFFRAST_ARCHIVE_SHA256 MIP_SPLATTING_COMMIT
echo "NVDIFFRAST_BUILD_STAGE=CUDA_PROBE_START"
"$CUPID_PYTHON" - <<'PY'
import json
import os
from pathlib import Path

import platformdirs
import packaging
import pandas
import PIL
from PIL import Image
import google.protobuf
import pydantic
import pydantic_core
import wandb
import scipy
import torch
import nvdiffrast.torch as dr
from diff_gaussian_rasterization import GaussianRasterizer, GaussianRasterizationSettings

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
    "platformdirs": platformdirs.__version__,
    "packaging": packaging.__version__,
    "pandas": pandas.__version__,
    "pillow": PIL.__version__,
    "protobuf": google.protobuf.__version__,
    "scipy": scipy.__version__,
    "pydantic": pydantic.__version__,
    "pydantic_core": pydantic_core.__version__,
    "diff_gaussian_rasterization": os.environ["MIP_SPLATTING_COMMIT"],
    "gpu": torch.cuda.get_device_name(),
    "probe_shape": list(raster.shape),
    "evidence_eligibility": "ENGINEERING_ONLY / NO_SCIENCE",
}
Path(os.environ["CUPID_NVDIFFRAST_OVERLAY"], "overlay_receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n"
)
print("NVDIFFRAST_OVERLAY_RECEIPT=" + json.dumps(receipt, sort_keys=True), flush=True)
PY
