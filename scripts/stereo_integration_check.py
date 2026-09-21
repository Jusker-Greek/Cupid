#!/usr/bin/env python3
"""CPU-only exact-checkout integration contract; no weights, targets, or GPU."""
import argparse
import importlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/stereo/train_stage1_smoke_1gpu.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    with open(args.config, encoding="utf-8") as handle:
        config = json.load(handle)
    required = ("experiment_id", "expected_world_size", "budget", "pretrained_init",
                "data_factory", "objective", "logger_factory", "eval_factory")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError("missing config keys: " + ",".join(missing))
    if config["experiment_id"] != "STEREO_CUPID_STAGE1_TRAIN_V1":
        raise ValueError("unexpected experiment identity")
    if config.get("configuration_state") == "BOUND_FOR_EXECUTION":
        raise ValueError("integration check does not certify a GPU-bound config")
    for module in ("cupid.trainers.stereo_stage1", "cupid.trainers.stereo_stage1_objective",
                   "cupid.trainers.stereo_stage1_logging", "cupid.stereo_observability.integration",
                   "cupid.datasets.stereo_gso"):
        importlib.import_module(module)
    if config["objective"]["name"] != "supervised_suv_fm":
        raise ValueError("unexpected objective")
    if config["trainable_parameter_groups"] != ["suv_flow"]:
        raise ValueError("unexpected trainable parameter contract")
    print(json.dumps({"status": "PASS", "scope": "CPU_INTERFACE_ONLY",
                      "experiment_id": config["experiment_id"], "config": args.config}))


if __name__ == "__main__":
    main()
