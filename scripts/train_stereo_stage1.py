#!/usr/bin/env python3
"""Launch with torchrun inside the R worker's registered Slurm allocation."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_config(path):
    """Small explicit JSON inheritance; child dictionaries replace parent keys."""
    path = Path(path).resolve(strict=True)
    with path.open() as handle:
        config = json.load(handle)
    parent = config.pop("extends", None)
    if parent is not None:
        parent_path = (path.parent / parent).resolve(strict=True)
        with parent_path.open() as handle:
            base = json.load(handle)
        if "extends" in base:
            raise ValueError("Only one explicit config inheritance level is supported")
        config = {**base, **config}
    return config


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
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], check=False).returncode != 0:
        raise RuntimeError("Tracked checkout modifications are forbidden")
    subprocess.run(["git", "ls-files", "--error-unmatch", "scripts/train_stereo_stage1.py"],
                   check=True, stdout=subprocess.DEVNULL)
    config = load_config(args.config)
    if config.get("configuration_state") != "BOUND_FOR_EXECUTION":
        raise ValueError("Bind asset hashes, dataset/target/split identity and budget before execution")
    from cupid.trainers.stereo_stage1 import run_training
    run_training(config, args.output_dir, args.resume_optimizer, args.stop_after_updates)


if __name__ == "__main__":
    main()
