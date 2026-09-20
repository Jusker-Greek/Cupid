#!/usr/bin/env python3
"""Inspect integrated source or frozen-V1 artifacts inside a Slurm allocation.

This produces engineering evidence only; it neither submits jobs nor accepts
scientific results. Run with a fresh --output receipt to preserve attempts.
"""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs/stereo_cupid_v1/lanes/I_DEPENDENCIES.json"


class ContractError(ValueError):
    pass


def require(predicate, message):
    if not predicate:
        raise ContractError(message)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def load_json(path):
    def reject_constant(value):
        raise ContractError(f"Non-standard JSON number: {value}")
    return json.loads(path.read_text(), parse_constant=reject_constant)


def source_check(args, report):
    manifest = load_json(args.manifest)
    report.update(manifest=str(args.manifest.resolve()), manifest_sha256=digest(args.manifest))
    require(manifest["gpu_submission_owner"] == "R", "GPU submission owner must remain R")
    require(manifest["frozen_experiment_id"] != manifest["training_experiment_id"], "Mixed experiment identities")
    # Match the repository's verified-bundle helper's read-only check. Avoid
    # git status on its fresh cluster mirror checkouts (reported legacy issue).
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=True)
    require(not git("ls-files", "--others", "--exclude-standard"), "Checkout has untracked files")
    base = manifest["base_commit"]
    require(git("rev-parse", f"{base}^{{tree}}") == manifest["base_tree"], "Base tree mismatch")
    changed = git("diff", "--name-only", base, "HEAD", "--", *manifest["frozen_paths"]).splitlines()
    report["frozen_paths_changed"] = changed
    require(not changed, "Frozen V1 paths changed: " + ", ".join(changed))
    # Parse added/modified Python without importing runtime/CUDA dependencies.
    parsed = []
    for name in git("diff", "--diff-filter=ACMRT", "--name-only", base, "HEAD").splitlines():
        if name.endswith(".py"):
            ast.parse((ROOT / name).read_text(), filename=name)
            parsed.append(name)
    report["python_files_parsed"] = parsed
    lane_results = {}
    for lane, item in manifest["lanes"].items():
        require(item["base_commit"] == base, f"{lane}: mismatched lane baseline")
        require(len(item["source_commits"]) == len(item["integrated_commits"]), f"{lane}: incomplete source→integration mapping")
        for commit in item["integrated_commits"]:
            subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True)
        for name in item["files"]:
            file = (ROOT / name).resolve()
            require(file.is_relative_to(ROOT), f"{lane}: file escapes checkout")
            require(file.is_file(), f"{lane}: integrated file missing: {name}")
        lane_results[lane] = {"state": item["state"], "source_commits": item["source_commits"],
                              "integrated_commits": item["integrated_commits"]}
    report["lanes"] = lane_results
    pending = [lane for lane in args.require_lane if not manifest["lanes"][lane]["integrated_commits"]]
    report["requested_lanes_missing"] = pending
    require(not pending, "Owner handoff not integrated: " + ", ".join(pending))
    report["scope"] = "SOURCE_CONTRACT_ONLY_NOT_RUNTIME"


def inference_check(args, report):
    # Lazy import keeps source checks independent of numpy/model dependencies.
    import numpy as np

    root = args.run_root.resolve(strict=True)
    receipt = load_json(root / "result.json")
    report["input_receipt"] = {"path": str(root / "result.json"), "sha256": digest(root / "result.json")}
    require(receipt["schema"] == "stereo_cupid/v1", "Not a frozen-V1 receipt")
    require(receipt["run_class"] == "PRETRAINED_STEREO_PILOT", "Unexpected inference run class")
    require(receipt["git_commit"] == args.run_commit, "Run commit does not match declared execution identity")
    require(str(receipt["slurm_job_id"]) == args.run_job, "Run JobID mismatch")
    require(receipt["scientific_claim"] == "UNTESTED", "Pilot receipt unexpectedly claims science")
    report.update(run_commit=args.run_commit, run_job=args.run_job,
                  model_status=receipt["status"], geometry_status=receipt.get("geometry_status", "UNVERIFIED"),
                  stage2_status=receipt.get("stage2_status", "UNVERIFIED"))
    require(receipt["status"] in ("COMPLETED", "PARTIAL"), "Model did not emit a completed/partial Stage1 artifact")
    archive = root / "stage1_and_geometry.npz"
    require(archive.is_file(), "Stage1 archive missing")
    with np.load(archive, allow_pickle=False) as arrays:
        support = arrays["support_coords"]
        require(support.ndim == 2 and support.shape[1] == 4, "support_coords must be [N,4]")
        require(np.issubdtype(support.dtype, np.integer), "Support coordinates must be integer")
        require(np.all(support[:, 0] == 0), "Support must use one shared batch-zero grid")
        require(len(np.unique(support, axis=0)) == len(support), "Duplicate support keys")
        n = len(support)
        for key, width in (("x_local", 3), ("uv_left", 2), ("uv_right", 2),
                           ("pixels_left", 2), ("pixels_right", 2)):
            require(arrays[key].shape == (n, width), f"{key}: mismatched support order/length")
            require(np.isfinite(arrays[key]).all(), f"{key}: nonfinite raw output")
        for key in ("uv_left", "uv_right"):
            require(np.all((arrays[key] >= 0) & (arrays[key] <= 1)), f"{key}: decoded sigmoid UV outside [0,1]")
        coords = arrays["coords"]
        require(coords.ndim == 2 and coords.shape[1] == 4, "coords must be [M,4]")
        require(set(map(tuple, coords)).issubset(set(map(tuple, support))), "Occupancy not contained in UV support")
        report.update(num_support=n, num_occupied=len(coords))
        if "valid" in arrays:
            valid = arrays["valid"]
            require(valid.shape == (n,) and valid.dtype == np.bool_, "Invalid geometry validity mask")
            require(receipt["num_input"] == n, "Geometry input denominator mismatch")
            require(receipt["num_valid"] == int(valid.sum()), "Geometry valid denominator mismatch")
            expected_filters = {"finite_input", "inside_images", "finite_solution", "positive_depth", "reprojection", "ray_angle"}
            require(set(receipt["filter_counts"]) == expected_filters, "Geometry filter set is incomplete")
            masks = []
            for name, count in receipt["filter_counts"].items():
                mask = arrays["mask_" + name]
                require(mask.shape == (n,) and mask.dtype == np.bool_, f"Invalid {name} filter mask")
                require(int(mask.sum()) == count, f"{name}: count mismatch")
                masks.append(mask)
            require(np.array_equal(valid, np.logical_and.reduce(masks)), "Validity is not the conjunction of recorded filters")
            for name, shape in (("disparity_px", (n,)), ("reprojection_px", (n, 2)), ("ray_angle_deg", (n,))):
                require(arrays[name].shape == shape, f"{name}: failed rows removed or wrong shape")
            points = arrays["points_left_camera"]
            require(points.shape == (n, 3), "Triangulation must preserve failed points in denominator")
            require(np.isfinite(points[valid]).all(), "Valid triangulated point is nonfinite")
            require(receipt["length_unit"] == receipt["camera_contract"]["length_unit"], "Geometry unit changed")
            report.update(num_geometry_valid=int(valid.sum()), length_unit=receipt["length_unit"])
        else:
            require(receipt["geometry_status"] == "CALIBRATION_MISSING", "Geometry masks missing without calibration status")
        if receipt.get("similarity") is not None:
            fit = receipt["similarity"]
            require(receipt["geometry_status"] == "OK", "Failed geometry exported a similarity")
            require(np.isfinite(fit["scale"]) and fit["scale"] > 0, "Invalid similarity scale")
            require(np.allclose(arrays["scale"], fit["scale"]), "Scale artifact disagrees with receipt")
            for field in ("rotation", "translation"):
                require(np.allclose(arrays[field], fit[field]), f"{field} artifact disagrees with receipt")
            require(fit["source_frame"] == "cupid_canonical" and fit["target_frame"] == "left_camera_opencv", "Similarity frame mismatch")
        else:
            require(receipt["geometry_status"] != "OK", "Geometry OK without similarity")
    report["archive_sha256"] = digest(archive)
    if receipt.get("full_mesh") and receipt.get("stage2_status") == "OK":
        mesh = root / "mesh_canonical.ply"
        require(mesh.is_file() and mesh.stat().st_size > 0, "Successful Stage2 missing mesh")
        require(receipt.get("canonical_mesh_transform_applied") is False, "Canonical mesh already transformed")
        report["canonical_mesh_sha256"] = digest(mesh)
    if receipt.get("placed_mesh"):
        placed = receipt["placed_mesh"]
        path = (root / placed["file"]).resolve()
        require(path.is_relative_to(root), "Placed mesh path escapes run root")
        require(path.is_file() and path.stat().st_size > 0, "Placed mesh missing")
        require(placed["transform_applied_once"] is True, "Unknown placement transform count")
        report["placed_mesh_sha256"] = digest(path)
    report["complete_model_path"] = receipt["status"] == "COMPLETED" and (
        not receipt.get("full_mesh") or receipt.get("stage2_status") == "OK")
    report["geometry_success"] = receipt["geometry_status"] == "OK"
    report["scope"] = "ARTIFACT_CONSISTENCY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    source = subparsers.add_parser("source")
    source.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    source.add_argument("--require-lane", action="append", choices=("D", "T", "L", "R"), default=[])
    inference = subparsers.add_parser("inference")
    inference.add_argument("--run-root", type=Path, required=True)
    inference.add_argument("--run-commit", required=True)
    inference.add_argument("--run-job", required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURMD_NODENAME"):
        parser.error("Execute only inside a Slurm compute allocation")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve before checking; never overwrite an earlier failed attempt.
    with args.output.open("x") as stream:
        report = {"schema": "stereo_cupid_integration_check/v1", "mode": args.mode,
                  "checked_at": datetime.now(timezone.utc).isoformat(), "host": socket.gethostname(),
                  "slurm_job_id": os.environ["SLURM_JOB_ID"], "evidence_eligibility": "ENGINEERING_ONLY_NO_SCIENCE"}
        try:
            report.update(checker_commit=git("rev-parse", "HEAD"), checker_tree=git("rev-parse", "HEAD^{tree}"))
            (source_check if args.mode == "source" else inference_check)(args, report)
            report["status"] = "PASS"
        except Exception as error:
            report.update(status="FAIL", first_failed_predicate=str(error), error_type=type(error).__name__)
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report, allow_nan=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
