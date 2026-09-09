#!/bin/bash

# Load the cluster-local credential source while keeping W&B explicitly online.
SECRETS_ENV="${XFACTOR_SECRETS_ENV:-${HOME}/.config/xfactor/secrets.env}"
if [ -f "${SECRETS_ENV}" ]; then
    set -a
    source "${SECRETS_ENV}"
    set +a
fi

export WANDB_MODE=online

if [ -z "${WANDB_API_KEY:-}" ] && [ ! -f "${HOME}/.netrc" ]; then
    echo "WANDB online credential source not found; refusing to run offline. See docs/cluster_secret_setup.md." >&2
    exit 1
fi
