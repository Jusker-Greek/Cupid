#!/usr/bin/env python3
"""CPU-only cross-module regression fixtures, never model/scientific evidence.

R may run this on Slurm. Fixtures are synthetic, use temporary directories and
test failure retention + frozen V1 -> L callback compatibility, not accuracy.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from stereo_integration_check import ContractError, inference_check


class CrossModuleContracts(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from cupid.utils.stereo_geometry import StereoCalibration, triangulate_and_fit
        self.directory = tempfile.TemporaryDirectory(prefix="stereo_integration_fixture_")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        # Deliberately wrong disparity: every point is rejected, but all rows
        # must survive export. No model or independent-GT claim is made.
        camera = {"K_left": [[100, 0, 20], [0, 100, 20], [0, 0, 1]],
                  "K_right": [[100, 0, 20], [0, 100, 20], [0, 0, 1]],
                  "right_from_left": [[1, 0, 0, -.1], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                  "image_size_left": [40, 40], "image_size_right": [40, 40],
                  "length_unit": "scene_unit", "source": "synthetic_contract_fixture",
                  "camera_convention": "opencv", "distortion": "none"}
        left = np.array([[10., 10.], [12., 10.], [10., 12.], [12., 12.]])
        right = left + [2., 0.]
        support = np.array([[0, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0]], dtype=np.int32)
        local = (support[:, 1:] + .5) / 2 - .5
        geometry = triangulate_and_fit(local, left, right, StereoCalibration.from_dict(camera))
        arrays = dict(coords=support, support_coords=support, x_local=local,
                      uv_left=left/40, uv_right=right/40, pixels_left=left, pixels_right=right)
        for key in ("valid", "points_left_camera", "disparity_px", "reprojection_px", "ray_angle_deg"):
            arrays[key] = geometry[key]
        arrays.update({"mask_"+key: value for key, value in geometry["masks"].items()})
        np.savez_compressed(self.root / "stage1_and_geometry.npz", **arrays)
        self.receipt = {"schema": "stereo_cupid/v1", "run_class": "PRETRAINED_STEREO_PILOT",
                        "git_commit": "synthetic_fixture_not_a_commit", "slurm_job_id": "synthetic_fixture",
                        "scientific_claim": "UNTESTED", "status": "COMPLETED", "full_mesh": False,
                        "geometry_status": geometry["status"], "stage2_status": "NOT_REQUESTED",
                        "camera_contract": camera, "length_unit": "scene_unit",
                        "num_input": 4, "num_valid": int(geometry["valid"].sum()),
                        "filter_counts": {key: int(value.sum()) for key, value in geometry["masks"].items()}}
        self.args = argparse.Namespace(run_root=self.root, run_commit=self.receipt["git_commit"],
                                       run_job=self.receipt["slurm_job_id"])
        self.save()

    def save(self):
        (self.root / "result.json").write_text(json.dumps(self.receipt, allow_nan=False))

    def test_failed_geometry_remains_reportable_without_becoming_science(self):
        report = {}
        inference_check(self.args, report)
        self.assertFalse(report["geometry_success"])
        self.assertEqual(report["num_support"], 4)
        self.assertEqual(report["num_geometry_valid"], 0)
        self.assertTrue(report["complete_model_path"])

    def test_removed_failure_denominator_is_rejected(self):
        self.receipt["num_input"] = 0
        self.save()
        with self.assertRaisesRegex(ContractError, "denominator"):
            inference_check(self.args, {})

    def test_scene_unit_cannot_be_relabelled_metres(self):
        self.receipt["length_unit"] = "m"
        self.save()
        with self.assertRaisesRegex(ContractError, "unit changed"):
            inference_check(self.args, {})

    def test_v1_failure_reaches_logger_with_full_evaluation_denominator(self):
        from cupid.stereo_observability.logger import logger_factory
        from cupid.stereo_observability.metrics import from_v1_result
        callback = logger_factory({"identity": {
            "experiment_id": "SYNTHETIC_CONTRACT_FIXTURE", "attempt_id": "synthetic_fixture",
            "git_commit": "synthetic_fixture", "git_tree": "synthetic_fixture", "slurm_job_id": "synthetic_fixture",
        }}, self.root / "logs", rank=0)
        callback("evaluation", 0, {"samples": [from_v1_result(self.receipt, "synthetic/pair/0")], "split": "inference"})
        events = [json.loads(line) for line in (self.root / "logs/stereo_observability/events.jsonl").read_text().splitlines()]
        self.assertEqual(events[0]["details"]["summary"]["num_expected"], 1)
        self.assertEqual(events[0]["details"]["summary"]["num_prediction_ok"], 0)
        self.assertIsNone(events[0]["details"]["summary"]["metrics"]["translation_error_m"]["mean"])


class TrainingInterfaces(unittest.TestCase):
    def test_engine_padding_weights_survive_D_collation(self):
        import torch
        from cupid.datasets.stereo_gso import collate_stage1_pairs
        from cupid.trainers.stereo_stage1 import ExactPairDataset
        source = [{"ss_latent": torch.zeros(8, 2, 2, 2), "pair_id": "synthetic/pair/0"}]
        wrapped = ExactPairDataset(source, seed=17, epoch=0)
        batch = collate_stage1_pairs([wrapped[(0, 1)], wrapped[(0, 0)]])
        self.assertIsInstance(batch["_pair_weight"], torch.Tensor)
        torch.testing.assert_close(batch["_pair_weight"].double(), torch.tensor([1., 0.], dtype=torch.float64))
        self.assertEqual(batch["pair_id"], ["synthetic/pair/0"] * 2)

    def test_L_eval_factory_accepts_T_keyword_contract(self):
        from cupid.stereo_observability.integration import eval_factory
        hook = eval_factory(config={}, output_dir="unused_no_write", rank=0)
        result = hook(model=None, step=0, context={})
        self.assertEqual(result["status"], "UNVERIFIED")


if __name__ == "__main__":
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURMD_NODENAME"):
        raise SystemExit("Run only on a Slurm compute node")
    unittest.main(verbosity=2)
