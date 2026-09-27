#!/usr/bin/env python3
"""Count GSO stereo assets and sample content on a Slurm CPU node."""
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


KINDS = ("left_png", "right_png", "left_npy", "right_npy", "depth_hdf5")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def indexed_files(directory: Path, suffixes: tuple[str, ...]) -> dict[str, dict[str, Path]]:
    result = {suffix: {} for suffix in suffixes}
    if not directory.is_dir():
        return result
    with os.scandir(directory) as entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            path = Path(entry.path)
            suffix = path.suffix.lower()
            if suffix not in result:
                continue
            key = str(int(path.stem)) if path.stem.isdigit() else path.stem
            if key in result[suffix]:
                raise ValueError(f"ambiguous frame alias: {directory}/{key}")
            result[suffix][key] = path
    return result


def sample_pair(object_id: str, trajectory: Path, frame: str, files: dict) -> dict:
    import h5py
    import numpy as np
    from PIL import Image

    sample = {"object_id": object_id, "trajectory": trajectory.name, "frame": frame}
    left, right = [], []
    for side in ("left", "right"):
        image_path = files[f"{side}_png"][frame]
        with Image.open(image_path) as image:
            image.load()
            if image.mode != "RGBA":
                raise ValueError(f"{image_path}: mode={image.mode}, expected RGBA")
            array = np.asarray(image)
        matrix_path = files[f"{side}_npy"][frame]
        matrix = np.load(matrix_path, allow_pickle=False)
        if matrix.shape not in ((3, 4), (4, 4)) or not np.isfinite(matrix).all():
            raise ValueError(f"{matrix_path}: invalid matrix shape/values")
        sample[side] = {
            "image_sha256": digest(image_path),
            "matrix_sha256": digest(matrix_path),
            "image_shape": list(array.shape),
            "matrix_shape": list(matrix.shape),
            "rotation_determinant": float(np.linalg.det(matrix[:3, :3])),
            "foreground_pixels": int((array[..., 3] > 127).sum()),
        }
        (left if side == "left" else right).append(array)
    depth_path = files["depth_hdf5"][frame]
    with h5py.File(depth_path, "r") as handle:
        depth = handle["depth"]
        if depth.shape != (2, *left[0].shape[:2]):
            raise ValueError(f"{depth_path}: depth shape {depth.shape}")
        sample["depth_shape"] = list(depth.shape)
        sample["depth_finite_positive_pixels"] = [
            int((np.isfinite(depth[i]) & (depth[i] > 0) & (depth[i] < 1e10)).sum())
            for i in (0, 1)
        ]
        if "colors" in handle:
            colors = handle["colors"]
            sample["hdf5_colors_match_png"] = bool(
                colors.shape == (2, *left[0].shape)
                and np.array_equal(colors[0], left[0])
                and np.array_equal(colors[1], right[0])
            )
    sample["depth_sha256"] = digest(depth_path)
    return sample


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-objects", type=int, default=64)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("run inside a Slurm allocation")
    if args.sample_objects < 1:
        parser.error("--sample-objects must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    objects = sorted(path for path in args.root.iterdir() if path.is_dir() and not path.is_symlink())
    selected = {objects[i].name for i in range(0, len(objects), max(1, len(objects) // args.sample_objects))}
    counts = Counter()
    samples, failures, mesh_samples = [], [], []
    receipt = {
        "schema": "STEREO_GSO_POPULATION_AUDIT_V1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "job_id": os.environ["SLURM_JOB_ID"],
        "host": socket.gethostname(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
        "root": str(args.root),
        "mesh_root": str(args.mesh_root),
        "scope": "full filename/metadata inventory plus deterministic cross-object content sample",
        "scientific_evidence": False,
        "target_ready": False,
        "selection": {"sample_objects_requested": args.sample_objects, "rule": "sorted objects at regular index interval; first complete frame of first and last trajectory"},
    }
    try:
        with (args.output / "objects.jsonl").open("x") as object_file:
            for obj in objects:
                obj_counts = Counter()
                mesh = args.mesh_root / obj.name / "meshes" / "model.obj"
                if mesh.is_file() and mesh.stat().st_size > 0:
                    counts["objects_with_mesh"] += 1
                    if obj.name in selected:
                        mesh_samples.append({"object_id": obj.name, "path": str(mesh), "sha256": digest(mesh)})
                trajectories = sorted(path for path in obj.iterdir() if path.is_dir() and not path.is_symlink())
                if trajectories:
                    counts["objects_with_trajectories"] += 1
                chosen_trajectories = {trajectories[0].name, trajectories[-1].name} if trajectories and obj.name in selected else set()
                for trajectory in trajectories:
                    obj_counts["trajectories"] += 1
                    metadata_path = trajectory / "trajectory_info.json"
                    try:
                        metadata = json.loads(metadata_path.read_text())
                        if not isinstance(metadata, dict):
                            raise ValueError("metadata must be an object")
                        obj_counts["metadata_readable"] += 1
                    except (OSError, ValueError, TypeError) as exc:
                        metadata = {}
                        obj_counts["metadata_invalid"] += 1
                        if len(failures) < 100:
                            failures.append({"path": str(metadata_path), "error": str(exc)})
                    try:
                        left = indexed_files(trajectory / "left", (".png", ".npy"))
                        right = indexed_files(trajectory / "right", (".png", ".npy"))
                        files = {"left_png": left[".png"], "right_png": right[".png"],
                                 "left_npy": left[".npy"], "right_npy": right[".npy"],
                                 "depth_hdf5": indexed_files(trajectory, (".hdf5",))[".hdf5"]}
                        all_frames = set().union(*(set(value) for value in files.values()))
                        complete_frames = set.intersection(*(set(value) for value in files.values()))
                        obj_counts["frame_candidates"] += len(all_frames)
                        obj_counts["five_asset_pairs"] += len(complete_frames)
                        obj_counts["incomplete_frame_candidates"] += len(all_frames - complete_frames)
                        for kind in KINDS:
                            obj_counts[kind] += len(files[kind])
                        if not all_frames:
                            obj_counts["empty_trajectories"] += 1
                        if metadata.get("num_frames") != len(complete_frames):
                            obj_counts["metadata_frame_count_mismatch"] += 1
                        if len(all_frames - complete_frames) and len(failures) < 100:
                            failures.append({"path": str(trajectory), "error": "missing asset stems", "missing_frames": len(all_frames - complete_frames)})
                        if trajectory.name in chosen_trajectories and complete_frames:
                            frame = sorted(complete_frames, key=lambda item: (not item.isdigit(), int(item) if item.isdigit() else item))[0]
                            try:
                                samples.append(sample_pair(obj.name, trajectory, frame, files))
                                obj_counts["sample_content_pass"] += 1
                            except (OSError, ValueError, KeyError, TypeError) as exc:
                                obj_counts["sample_content_fail"] += 1
                                samples.append({"object_id": obj.name, "trajectory": trajectory.name, "frame": frame, "error": str(exc)})
                    except (OSError, ValueError) as exc:
                        obj_counts["trajectory_scan_fail"] += 1
                        if len(failures) < 100:
                            failures.append({"path": str(trajectory), "error": str(exc)})
                counts.update(obj_counts)
                object_file.write(json.dumps({"object_id": obj.name, "mesh_present": mesh.is_file(), "counts": dict(obj_counts)}) + "\n")
                if counts["objects_scanned"] % 25 == 0:
                    print(json.dumps({"objects_scanned": counts["objects_scanned"], "five_asset_pairs": counts["five_asset_pairs"]}), flush=True)
                counts["objects_scanned"] += 1
        receipt["status"] = "COMPLETED"
    except Exception as exc:
        receipt["status"] = "FAILED"
        receipt["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        receipt.update(
            ended_at=datetime.now(timezone.utc).isoformat(),
            counts=dict(counts),
            sampled_pairs=len(samples),
            sampled_content_pass=sum("error" not in item for item in samples),
            sampled_content_fail=sum("error" in item for item in samples),
            object_index_sha256=digest(args.output / "objects.jsonl") if (args.output / "objects.jsonl").exists() else None,
        )
        (args.output / "content_samples.json").write_text(json.dumps(samples, indent=2) + "\n")
        (args.output / "mesh_samples.json").write_text(json.dumps(mesh_samples, indent=2) + "\n")
        (args.output / "failure_examples.json").write_text(json.dumps(failures, indent=2) + "\n")
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
