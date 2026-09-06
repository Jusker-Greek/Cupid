#!/usr/bin/env bash
set -euo pipefail

: "${CUPID_SOURCE_OVERLAY:?CUPID_SOURCE_OVERLAY is required}"
: "${CUPID_OUTPUT_OVERLAY:?CUPID_OUTPUT_OVERLAY is required}"
: "${CUPID_KAOLIN_WHEELHOUSE:?CUPID_KAOLIN_WHEELHOUSE is required}"
: "${CUPID_KAOLIN_WHEEL_MANIFEST:?CUPID_KAOLIN_WHEEL_MANIFEST is required}"

CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
KAOLIN_WHEEL_URL="${KAOLIN_WHEEL_URL:-http://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.4.1_cu118/kaolin-0.18.0-cp312-cp312-linux_x86_64.whl}"
KAOLIN_WHEEL_SHA256="${KAOLIN_WHEEL_SHA256:-6339c695a099d3907aa39bb63cc51381ba4cd8a05813ef466da850156052c153}"
partial_overlay="${CUPID_OUTPUT_OVERLAY}.partial"
temp_dir="$(mktemp -d /tmp/cupid_kaolin.XXXXXX)"
wheel_path="$temp_dir/kaolin-0.18.0-cp312-cp312-linux_x86_64.whl"

cleanup() {
    rm -rf "$temp_dir"
}
trap cleanup EXIT

test -d "$CUPID_SOURCE_OVERLAY"
test -d "$CUPID_KAOLIN_WHEELHOUSE"
test -f "$CUPID_KAOLIN_WHEEL_MANIFEST"
test ! -e "$CUPID_OUTPUT_OVERLAY"
test ! -e "$partial_overlay"

(cd "$CUPID_KAOLIN_WHEELHOUSE" && sha256sum -c "$CUPID_KAOLIN_WHEEL_MANIFEST")

cp -al "$CUPID_SOURCE_OVERLAY" "$partial_overlay"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
direct_hosts="nvidia-kaolin.s3.us-east-2.amazonaws.com,pypi.org,files.pythonhosted.org"
export no_proxy="${no_proxy:+$no_proxy,}$direct_hosts"
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}$direct_hosts"
download_complete=0
for attempt in 1 2 3 4 5 6; do
    current_bytes="$(stat -c '%s' "$wheel_path" 2>/dev/null || printf '0')"
    printf 'KAOLIN_DOWNLOAD_ATTEMPT=%s|RESUME_FROM=%s\n' "$attempt" "$current_bytes"
    if curl --fail --location --continue-at - \
        --connect-timeout 15 --max-time 240 \
        "$KAOLIN_WHEEL_URL" -o "$wheel_path"; then
        download_complete=1
        break
    fi
done
test "$download_complete" -eq 1

actual_sha256="$(sha256sum "$wheel_path" | awk '{print $1}')"
test "$actual_sha256" = "$KAOLIN_WHEEL_SHA256"
printf 'KAOLIN_WHEEL_SHA256=%s\n' "$actual_sha256"
"$CUPID_PYTHON" -m pip install \
    --target "$partial_overlay" --no-deps --no-index "$wheel_path"

missing_specs=()
require_package() {
    local module="$1"
    local spec="$2"
    if PYTHONPATH="$partial_overlay" "$CUPID_PYTHON" -c "import $module" \
        >/dev/null 2>&1; then
        printf 'DEPENDENCY_PRESENT=%s\n' "$module"
    else
        missing_specs+=("$spec")
    fi
}

require_package packaging 'packaging==26.3'
require_package typing_extensions 'typing-extensions==4.16.0'
require_package mypy_extensions 'mypy-extensions==1.1.0'
require_package wrapt 'wrapt==2.4.0'
require_package marshmallow 'marshmallow==3.26.2'
require_package typing_inspect 'typing-inspect==0.9.0'
require_package dataclasses_json 'dataclasses-json==0.6.7'
require_package deprecated 'Deprecated==1.3.1'
require_package pygltflib 'pygltflib==1.16.5'
require_package pxr 'usd-core==26.8'
require_package warp 'warp-lang==1.8.1'

if ((${#missing_specs[@]})); then
    printf 'DEPENDENCY_INSTALL=%s\n' "${missing_specs[*]}"
    "$CUPID_PYTHON" -m pip install \
        --target "$partial_overlay" --no-deps --no-index \
        --find-links "$CUPID_KAOLIN_WHEELHOUSE" "${missing_specs[@]}"
fi

PYTHONPATH="$partial_overlay" "$CUPID_PYTHON" -c \
    'import kaolin, torch; from kaolin.utils.testing import check_tensor; print(f"KAOLIN_IMPORT_OK={kaolin.__version__}|TORCH={torch.__version__}|CUDA={torch.version.cuda}|CHECK_TENSOR={check_tensor.__module__}.{check_tensor.__name__}")'

mv "$partial_overlay" "$CUPID_OUTPUT_OVERLAY"
printf 'OVERLAY_READY=%s\n' "$CUPID_OUTPUT_OVERLAY"
