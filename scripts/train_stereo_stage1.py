#!/usr/bin/env python3
"""Launch with torchrun inside the R worker's registered Slurm allocation."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True, help="Fresh attempt root, also when resuming")
    parser.add_argument("--resume-optimizer", help="Trusted Stage1 full-state checkpoint; never official safetensors")
    parser.add_argument("--stop-after-updates", type=int, help="Bound attempt without changing the frozen total budget")
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != args.expected_commit:
        raise RuntimeError("Checkout is not the exact registered GitHub commit")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        raise RuntimeError("Tracked checkout modifications are forbidden")
    with open(args.config) as handle:
        config = json.load(handle)
    if config.get("configuration_state") != "BOUND_FOR_EXECUTION":
        raise ValueError("Bind asset hashes, dataset/target/split identity and budget before execution")
    from cupid.trainers.stereo_stage1 import run_training
    run_training(config, args.output_dir, args.resume_optimizer, args.stop_after_updates)


if __name__ == "__main__":
    main()
