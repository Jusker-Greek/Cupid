#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_ROOT:?}"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
export http_proxy=http://hkuhpc.com:7999 https_proxy=http://hkuhpc.com:7999
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
overlay=/public/home/ricky/ENVIRONMENT/stereo_gso_open3d_cpu_0190_py312_a1
test ! -e "$overlay"
mkdir -p "${OUTPUT_ROOT:?}/wheels" "$overlay"
"$runtime/bin/python3" -m pip download --only-binary=:all: --no-deps \
  --retries 5 --timeout 60 --dest "$OUTPUT_ROOT/wheels" 'open3d-cpu==0.19.0'
wheel="$OUTPUT_ROOT/wheels/open3d_cpu-0.19.0-cp312-cp312-manylinux_2_31_x86_64.whl"
test -f "$wheel"
sha256sum "$wheel" | tee "$OUTPUT_ROOT/wheel.sha256"
"$runtime/bin/python3" -m pip install --no-deps --no-index --find-links "$OUTPUT_ROOT/wheels" \
  --target "$overlay" 'open3d-cpu==0.19.0'
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$overlay:$REPO_ROOT:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" - <<'PY'
import json
import open3d as o3d
import numpy as np
print(json.dumps({'open3d_version': o3d.__version__, 'numpy_version': np.__version__,
                  'open3d_path': o3d.__file__}), flush=True)
PY
