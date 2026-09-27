#!/usr/bin/env python3
"""Hash-compare every inventoried Gazebo GSO mesh with the shared GSO mesh copy."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess

from stereo_gso_population_audit import digest


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--object-index", type=Path, required=True)
    parser.add_argument("--left-root", type=Path, required=True)
    parser.add_argument("--right-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("run inside a Slurm allocation")
    args.output.mkdir(parents=True, exist_ok=False)
    counts = Counter()
    seen = set()
    with args.object_index.open() as source, (args.output / "mesh_comparisons.jsonl").open("x") as sink:
        for line in source:
            object_id = json.loads(line)["object_id"]
            if object_id in seen or Path(object_id).name != object_id or object_id in (".", ".."):
                raise ValueError(f"invalid or duplicate object ID: {object_id}")
            seen.add(object_id)
            left = args.left_root / object_id / "meshes" / "model.obj"
            right = args.right_root / object_id / "meshes" / "model.obj"
            row = {"object_id": object_id}
            for side, path in (("left", left), ("right", right)):
                row[side + "_path"] = str(path)
                if path.is_file() and path.stat().st_size > 0:
                    row[side + "_size"] = path.stat().st_size
                    row[side + "_sha256"] = digest(path)
                    counts[side + "_present"] += 1
                else:
                    row[side + "_error"] = "missing or empty"
            if "left_sha256" in row and "right_sha256" in row:
                if row["left_sha256"] == row["right_sha256"]:
                    counts["byte_equal"] += 1
                else:
                    counts["different"] += 1
            sink.write(json.dumps(row) + "\n")
            counts["objects"] += 1
            if counts["objects"] % 100 == 0:
                print(json.dumps(dict(counts)), flush=True)
    receipt = {
        "schema": "STEREO_GSO_MESH_COPY_AUDIT_V1",
        "job_id": os.environ["SLURM_JOB_ID"], "host": socket.gethostname(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "object_index_sha256": digest(args.object_index),
        "left_root": str(args.left_root), "right_root": str(args.right_root),
        "counts": dict(counts),
        "comparisons_sha256": digest(args.output / "mesh_comparisons.jsonl"),
        "canonical_mapping_verified": False,
        "scientific_evidence": False,
        "target_ready": False,
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
