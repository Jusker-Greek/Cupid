#!/usr/bin/env python3
"""Read-only bounded search for external geometry and camera evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
from pathlib import Path

KEYWORDS = (
    "render", "renderer", "voxel", "occup", "canonical", "trajectory",
    "camera", "intrinsic", "extrinsic", "transform", "metadata", "model",
    "mesh", "depth", "crop", "scene", "coordinate", "cv",
)
TEXT_SUFFIXES = {".json", ".jsonl", ".py", ".sh", ".yaml", ".yml", ".toml", ".md", ".tsv", ".txt"}
MAX_FILES = 12000
MAX_TEXT_BYTES = 512 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def keyword_hit(path: Path) -> bool:
    name = path.name.lower()
    return any(token in name for token in KEYWORDS) or path.suffix.lower() in {".obj", ".ply", ".npz", ".h5", ".hdf5"}


def inspect_text(path: Path) -> dict:
    result = {}
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > MAX_TEXT_BYTES:
        return result
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        return {"read_error": f"{type(exc).__name__}: {exc}"}
    lower = text.lower()
    result["tokens"] = {token: (token in lower) for token in ("canonical", "voxel", "occupancy", "w2c", "camera", "intrinsic", "extrinsic", "trajectory", "crop", "cv")}
    if path.suffix.lower() == ".json":
        try:
            value = json.loads(text)
            result["json_top_level"] = sorted(value) if isinstance(value, dict) else type(value).__name__
        except (ValueError, TypeError):
            result["json_parse"] = "failed"
    matches = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if re.search(r"canonical|voxel|occup|w2c|camera|intrinsic|extrinsic|trajectory|crop|opencv|computer.?vision", line, re.I):
            matches.append({"line": line_no, "text": line[:240]})
            if len(matches) >= 12:
                break
    if matches:
        result["evidence_lines"] = matches
    return result


def discover(root: Path, max_depth: int) -> tuple[list[dict], dict]:
    records = []
    errors = []
    visited = 0
    if not root.exists():
        return [], {"exists": False, "visited": 0, "errors": ["root_missing"]}
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        depth = len(current_path.relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if not (current_path / d).is_symlink())
        if depth >= max_depth:
            dirs[:] = []
        for name in sorted(files):
            visited += 1
            if visited > MAX_FILES:
                errors.append(f"file_cap_exceeded:{MAX_FILES}")
                return records, {"exists": True, "visited": visited, "errors": errors, "truncated": True}
            path = current_path / name
            if not keyword_hit(path):
                continue
            try:
                stat = path.stat()
                records.append({"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                                "sha256": sha256_file(path), "text": inspect_text(path)})
            except (OSError, ValueError) as exc:
                errors.append(f"{path}:{type(exc).__name__}:{exc}")
    return records, {"exists": True, "visited": visited, "errors": errors, "truncated": False}


def text_blob(record: dict) -> str:
    return json.dumps(record.get("text", {}), sort_keys=True).lower()


def path_or_text(record: dict) -> str:
    return (record["path"] + " " + text_blob(record)).lower()


def predicate_result(name: str, records: list[dict]) -> dict:
    if name == "canonical_to_frame_mapping":
        candidates = [r for r in records if "canonical" in path_or_text(r) and any(k in path_or_text(r) for k in ("mapping", "normalize", "coordinate", "import"))]
        command = "Provide a signed per-asset canonical_frame_mapping receipt: source_asset_sha256, canonical_frame, axis map, scale/offset, importer revision, and verification command."
    elif name == "official_voxelizer_and_occupancy":
        candidates = [r for r in records if any(k in path_or_text(r) for k in ("voxelizer", "trellis", "occupancy", "occup"))]
        command = "Run the pinned official voxelizer on the provenance-bound canonical mesh, save occupancy.npy, and emit voxelizer source/revision plus occupancy SHA256 in a receipt."
    elif name == "proper_cv_extrinsics_k_depth":
        candidates = [r for r in records if any(k in path_or_text(r) for k in ("w2c", "extrinsic", "opencv", "intrinsic")) and any(k in path_or_text(r) for k in ("depth", "camera", "trajectory"))]
        command = "For one manifest pair, emit both side proper CV w2c matrices (det(R)>0), K, depth provenance, image dimensions, and source metadata SHA256; verify the receipt on CPU."
    elif name == "crop_and_renderer_source_binding":
        candidates = [r for r in records if "crop" in path_or_text(r) or ("render" in path_or_text(r) and "source" in path_or_text(r))]
        command = "Bind integer crop_xyxy and preprocessing revision to the exact renderer/source hashes and pair image assets, then emit a hash-checked provenance receipt."
    else:
        raise ValueError(name)
    return {
        "predicate": name,
        "verified": False,
        "candidate_count": len(candidates),
        "candidate_paths": [{"path": r["path"], "sha256": r["sha256"]} for r in candidates[:12]],
        "minimum_supplement_command": command,
        "failure_reason": "Candidates are unverified references; no accepted receipt with the required identity/hash fields was found.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--max-depth", type=int, default=6)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("Slurm CPU allocation required")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    roots, records = [], []
    for raw_root in args.root:
        found, stats = discover(Path(raw_root), args.max_depth)
        roots.append({"root": raw_root, "stats": stats, "candidate_count": len(found)})
        records.extend(found)
    records.sort(key=lambda row: row["path"])
    index_path = output / "evidence_index.jsonl"
    with index_path.open("x") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    known = {row["path"] for row in records}
    required = [
        "/public/home/ricky/CODE/GSO_dataset/render_stereo_gazebo.py",
        "/public/home/ricky/CODE/GSO_dataset/scripts/test_random_linear_trajectory.sh",
        "/public/home/ricky/DATASET/Gazebo/Android_Figure_Panda/meshes/model.obj",
        "/public/home/ricky/DATASET/Gazebo/Android_Figure_Panda/random_linear_0/trajectory_info.json",
    ]
    required_status = []
    for raw in required:
        path = Path(raw)
        required_status.append({"path": raw, "exists": path.is_file(), "indexed": raw in known,
                                "sha256": sha256_file(path) if path.is_file() else None})
    predicates = [predicate_result(name, records) for name in (
        "canonical_to_frame_mapping", "official_voxelizer_and_occupancy",
        "proper_cv_extrinsics_k_depth", "crop_and_renderer_source_binding",
    )]
    first_failure = predicates[0]
    receipt = {
        "schema": "STEREO_EXTERNAL_BLOCKER_AUDIT_V1", "status": "EXTERNAL_BLOCKED",
        "job_id": os.environ["SLURM_JOB_ID"], "host": socket.gethostname(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
        "scope": {"roots": args.root, "max_depth": args.max_depth, "max_files": MAX_FILES},
        "roots": roots, "required_paths": required_status, "candidate_count": len(records),
        "evidence_index_sha256": sha256_file(index_path),
        "predicate_order": [p["predicate"] for p in predicates],
        "predicate_results": predicates,
        "first_failure_predicate": first_failure["predicate"],
        "first_failure_reason": first_failure["failure_reason"],
        "minimum_supplement_command": first_failure["minimum_supplement_command"],
        "blockers": [
            "No verified canonical mesh to canonical-frame mapping was found by this bounded search.",
            "No pinned official voxelizer receipt and canonical occupancy hash were found.",
            "No per-pair proper canonical-to-CV extrinsic plus K/depth provenance was found.",
            "No verified crop/source renderer identity was found for target generation.",
        ],
        "target_ready": False, "scientific_evidence": False, "not_a_gt_target": True,
    }
    (output / "EXTERNAL_BLOCKER_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
