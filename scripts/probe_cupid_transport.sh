#!/usr/bin/env bash
#SBATCH --job-name=stereo_cupid_transport
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=256M
#SBATCH --time=00:03:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_cupid_transport_%j.out
set -euo pipefail
: "${SLURM_JOB_ID:?Use a Slurm compute allocation}"
: "${CUPID_PROJECT_DIR:?}"
: "${CUPID_EXPECTED_COMMIT:?}"
cd "$CUPID_PROJECT_DIR"
test "$(git rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
git diff --quiet HEAD
printf 'JOB=%s HOST=%s COMMIT=%s\n' "$SLURM_JOB_ID" "$(hostname)" "$CUPID_EXPECTED_COMMIT"
base=https://huggingface.co/hbb1/Cupid/resolve/1191de37cc33b60273a631d4e07fbbe7cee798c1
for route in cluster_proxy direct; do
    if [[ "$route" == cluster_proxy ]]; then
        transport=(--proxy http://hkuhpc.com:7999 --noproxy '')
    else
        transport=(--proxy '' --noproxy '*')
    fi
    for target in config weight_range; do
        if [[ "$target" == config ]]; then
            url="$base/pipeline.json"
            limits=(--max-filesize 4096)
        else
            url="$base/ckpts/slat_flow_img_dit_L_64l8p2_fp16.safetensors"
            limits=(--range 0-1048575 --max-filesize 1048576)
        fi
        printf 'PROBE route=%s target=%s ' "$route" "$target"
        # Never print redirects, response bodies, request headers or credentials.
        # Bound each public download and discard bytes on the compute node.
        rc=0
        curl "${transport[@]}" "${limits[@]}" --location --silent \
            --connect-timeout 5 --max-time 35 --output /dev/null \
            --write-out 'HTTP=%{http_code} bytes=%{size_download} seconds=%{time_total} ' \
            "$url" || rc=$?
        printf 'exit=%s\n' "$rc"
    done
done
