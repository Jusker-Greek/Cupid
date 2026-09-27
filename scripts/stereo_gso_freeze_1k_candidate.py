#!/usr/bin/env python3
"""Freeze 1,000 content-readable GSO stereo candidates across objects."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

from cupid.datasets.stereo_gso import object_split
from stereo_gso_population_audit import digest, indexed_files, sample_pair


KINDS = ("left_png", "right_png", "left_npy", "right_npy", "depth_hdf5")


def candidates(root: Path, object_id: str, failures: list[dict]):
    obj = root / object_id
    if not obj.is_dir() or obj.is_symlink():
        return
    for trajectory in sorted(path for path in obj.iterdir() if path.is_dir() and not path.is_symlink()):
        metadata_path = trajectory / "trajectory_info.json"
        try:
            metadata = json.loads(metadata_path.read_text())
            if not isinstance(metadata, dict):
                raise ValueError("metadata must be an object")
            left = indexed_files(trajectory / "left", (".png", ".npy"))
            right = indexed_files(trajectory / "right", (".png", ".npy"))
            files = {
                "left_png": left[".png"], "left_npy": left[".npy"],
                "right_png": right[".png"], "right_npy": right[".npy"],
                "depth_hdf5": indexed_files(trajectory, (".hdf5",))[".hdf5"],
            }
            complete = set.intersection(*(set(paths) for paths in files.values()))
            if not complete or metadata.get("num_frames") != len(complete):
                raise ValueError("empty or incomplete trajectory")
            frame = min(complete, key=lambda item: (not item.isdigit(), int(item) if item.isdigit() else item))
            sample = sample_pair(object_id, trajectory, frame, files)
            if not sample.get("hdf5_colors_match_png", False):
                raise ValueError("HDF5 colors differ from PNG")
            if any(value <= 0 for value in sample["depth_finite_positive_pixels"]):
                raise ValueError("no positive foreground depth")
            yield {
                "schema": "STEREO_GSO_1K_CANDIDATE_V1",
                "pair_id": f"GSO_1K_200/{object_id}/{trajectory.name}/{frame}",
                "object_id": object_id, "trajectory_id": trajectory.name, "frame_id": frame,
                "split": object_split(object_id),
                "assets": {kind: str(files[kind][frame].relative_to(root)) for kind in KINDS},
                "metadata_path": str(metadata_path.relative_to(root)),
                "metadata_sha256": digest(metadata_path),
                "metadata": metadata,
                "content_diagnostics": sample,
                "content_verified": True,
                "calibration_verified": False,
                "training_target_ready": False,
            }
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if len(failures) < 100:
                failures.append({"object_id": object_id, "trajectory": trajectory.name, "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--population-receipt", type=Path, required=True)
    parser.add_argument("--object-index", type=Path, required=True)
    parser.add_argument("--mesh-comparisons", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=1000)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("run inside a Slurm allocation")
    if os.environ.get("HDF5_USE_FILE_LOCKING") != "FALSE":
        parser.error("HDF5_USE_FILE_LOCKING=FALSE is required")
    if args.pairs < 1:
        parser.error("--pairs must be positive")
    population = json.loads(args.population_receipt.read_text())
    if population.get("status") != "COMPLETED" or population.get("root") != str(args.root):
        parser.error("population receipt does not match root")
    if digest(args.object_index) != population.get("object_index_sha256"):
        parser.error("object index hash does not match population receipt")
    objects = [json.loads(line)["object_id"] for line in args.object_index.read_text().splitlines()]
    if len(objects) != len(set(objects)) or objects != sorted(objects):
        parser.error("object index is not unique and sorted")
    mesh_rows = {row["object_id"]: row for row in (json.loads(line) for line in args.mesh_comparisons.read_text().splitlines())}
    if set(mesh_rows) != set(objects):
        parser.error("mesh comparison object IDs differ from population index")
    args.output.mkdir(parents=True, exist_ok=False)
    failures: list[dict] = []
    first, second = [], []
    for index, object_id in enumerate(objects):
        for rank, row in enumerate(candidates(args.root, object_id, failures)):
            row["mesh_sha256"] = mesh_rows[object_id].get("left_sha256")
            row["shared_mesh_byte_equal"] = row["mesh_sha256"] == mesh_rows[object_id].get("right_sha256")
            (first if rank == 0 else second).append(row)
            if rank >= 1:
                break
        if (index + 1) % 100 == 0:
            print(json.dumps({"objects_scanned": index + 1, "first_pairs": len(first), "second_pairs": len(second)}), flush=True)
    if len(first) > args.pairs or len(first) + len(second) < args.pairs:
        raise ValueError(f"cannot cover {len(first)} objects in {args.pairs} pairs with {len(second)} second pairs")
    second.sort(key=lambda row: (hashlib.sha256(row["object_id"].encode()).hexdigest(), row["pair_id"]))
    selected = first + second[:args.pairs - len(first)]
    selected.sort(key=lambda row: (row["object_id"], row["trajectory_id"], row["frame_id"]))
    with (args.output / "pairs.jsonl").open("x") as handle:
        for row in selected:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (args.output / "failure_examples.json").write_text(json.dumps(failures, indent=2) + "\n")
    receipt = {
        "schema": "STEREO_GSO_1K_CANDIDATE_RECEIPT_V1",
        "status": "CANDIDATE_ONLY",
        "job_id": os.environ["SLURM_JOB_ID"], "host": socket.gethostname(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "root": str(args.root),
        "population_receipt_sha256": digest(args.population_receipt),
        "object_index_sha256": digest(args.object_index),
        "mesh_comparisons_sha256": digest(args.mesh_comparisons),
        "selection": "one content-readable pair per object, then SHA256(object_id)-ordered second distinct trajectory until requested count",
        "requested_pairs": args.pairs, "selected_pairs": len(selected),
        "selected_objects": len(first), "second_trajectory_pairs": len(selected) - len(first),
        "split_pairs": dict(Counter(row["split"] for row in selected)),
        "split_objects": dict(Counter(row["split"] for row in first)),
        "all_shared_mesh_equal": all(row["shared_mesh_byte_equal"] for row in selected),
        "all_saved_rotations_proper": all(
            row["content_diagnostics"][side]["rotation_determinant"] > 0
            for row in selected for side in ("left", "right")
        ),
        "pairs_sha256": digest(args.output / "pairs.jsonl"),
        "scientific_evidence": False, "training_target_ready": False,
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
