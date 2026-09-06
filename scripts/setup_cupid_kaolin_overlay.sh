#!/usr/bin/env bash
set -euo pipefail

: "${CUPID_SOURCE_OVERLAY:?CUPID_SOURCE_OVERLAY is required}"
: "${CUPID_OUTPUT_OVERLAY:?CUPID_OUTPUT_OVERLAY is required}"

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
test ! -e "$CUPID_OUTPUT_OVERLAY"
test ! -e "$partial_overlay"

cp -al "$CUPID_SOURCE_OVERLAY" "$partial_overlay"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
export no_proxy="${no_proxy:+$no_proxy,}nvidia-kaolin.s3.us-east-2.amazonaws.com"
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}nvidia-kaolin.s3.us-east-2.amazonaws.com"
curl --fail --location --retry 4 --retry-all-errors \
    --connect-timeout 15 --max-time 300 \
    "$KAOLIN_WHEEL_URL" -o "$wheel_path"

actual_sha256="$(sha256sum "$wheel_path" | awk '{print $1}')"
test "$actual_sha256" = "$KAOLIN_WHEEL_SHA256"
"$CUPID_PYTHON" -m pip install \
    --target "$partial_overlay" --no-deps --no-index "$wheel_path"

PYTHONPATH="$partial_overlay" "$CUPID_PYTHON" -c \
    'import kaolin, torch; from kaolin.utils.testing import check_tensor; print(f"KAOLIN_IMPORT_OK={kaolin.__version__}|TORCH={torch.__version__}|CUDA={torch.version.cuda}|CHECK_TENSOR={check_tensor.__module__}.{check_tensor.__name__}")'

mv "$partial_overlay" "$CUPID_OUTPUT_OVERLAY"
printf 'OVERLAY_READY=%s\n' "$CUPID_OUTPUT_OVERLAY"
