#!/usr/bin/env python3
"""Retry only HDF5 lock failures from an immutable population-audit receipt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess

from stereo_gso_population_audit import digest, indexed_files, sample_pair


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("run inside a Slurm allocation")
    if os.environ.get("HDF5_USE_FILE_LOCKING") != "FALSE":
        parser.error("HDF5_USE_FILE_LOCKING=FALSE is required")
    args.output.mkdir(parents=True, exist_ok=False)
    source_receipt = args.source / "receipt.json"
    source_samples = args.source / "content_samples.json"
    source = json.loads(source_receipt.read_text())
    if source.get("status") != "COMPLETED" or source.get("root") != str(args.root):
        parser.error("source receipt does not match completed population audit")
    failures = [item for item in json.loads(source_samples.read_text()) if "error" in item]
    if not failures or any("No locks available" not in item["error"] for item in failures):
        parser.error("expected only HDF5 lock failures")
    retries = []
    for item in failures:
        trajectory = args.root / item["object_id"] / item["trajectory"]
        left = indexed_files(trajectory / "left", (".png", ".npy"))
        right = indexed_files(trajectory / "right", (".png", ".npy"))
        files = {
            "left_png": left[".png"], "left_npy": left[".npy"],
            "right_png": right[".png"], "right_npy": right[".npy"],
            "depth_hdf5": indexed_files(trajectory, (".hdf5",))[".hdf5"],
        }
        try:
            retries.append(sample_pair(item["object_id"], trajectory, item["frame"], files))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            retries.append({**{key: item[key] for key in ("object_id", "trajectory", "frame")}, "error": str(exc)})
    (args.output / "content_retries.json").write_text(json.dumps(retries, indent=2) + "\n")
    receipt = {
        "schema": "STEREO_GSO_HDF5_LOCK_RETRY_V1",
        "job_id": os.environ["SLURM_JOB_ID"], "host": socket.gethostname(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_job_id": source["job_id"],
        "source_receipt_sha256": digest(source_receipt),
        "source_content_samples_sha256": digest(source_samples),
        "retry_count": len(retries),
        "pass": sum("error" not in item for item in retries),
        "fail": sum("error" in item for item in retries),
        "target_ready": False, "scientific_evidence": False,
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
