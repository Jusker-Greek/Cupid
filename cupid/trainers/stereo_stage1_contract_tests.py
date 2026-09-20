"""CPU sampler/resume interface fixtures; not a model/GPU smoke.

Run only on a Slurm compute node:
python -m cupid.trainers.stereo_stage1_contract_tests
"""
import os
import random
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import torch

from .stereo_stage1 import ExactBatchSampler, ExactPairDataset, materialize_prediction_samples
from .stereo_stage1_logging import Stage1LoggingAdapter
from ..datasets.stereo_gso import collate_stage1_pairs
from ..stereo_observability.integration import eval_factory
from ..stereo_observability.metrics import METRICS


class RandomCPUData:
    def __len__(self):
        return 7

    def __getitem__(self, index):
        return {"index": index, "random": torch.tensor([random.random(), np.random.rand(), torch.rand(()).item()])}


class SamplerContract(unittest.TestCase):
    def test_complete_unique_epoch_uneven_partitions(self):
        for size in (1, 2, 3, 7, 20):
            for world in (1, 2):
                for batch_size in (1, 3):
                    ranks = [list(ExactBatchSampler(size, batch_size, rank, world, 42, 3)) for rank in range(world)]
                    self.assertEqual(len({len(batches) for batches in ranks}), 1)
                    observed = [index for batches in ranks for batch in batches for index, weight in batch if weight]
                    self.assertEqual(sorted(observed), list(range(size)))
                    self.assertTrue(all(len(batch) == batch_size for batches in ranks for batch in batches))

    def test_resume_is_exact_remaining_batch_suffix(self):
        for rank in (0, 1):
            batches = list(ExactBatchSampler(11, 2, rank, 2, 43, 7))
            for cursor in range(len(batches) + 1):
                resumed = list(ExactBatchSampler(11, 2, rank, 2, 43, 7, start=cursor))
                self.assertEqual(resumed, batches[cursor:])

    def test_cpu_sample_rng_replays_and_does_not_change_caller_rng(self):
        dataset = ExactPairDataset(RandomCPUData(), seed=12, epoch=3)
        random.seed(11)
        np.random.seed(11)
        torch.manual_seed(11)
        expected = (random.random(), np.random.rand(), torch.rand(()))
        random.seed(11)
        np.random.seed(11)
        torch.manual_seed(11)
        first = dataset[(4, 1)]
        actual = (random.random(), np.random.rand(), torch.rand(()))
        self.assertEqual(expected[:2], actual[:2])
        self.assertTrue(torch.equal(expected[2], actual[2]))
        self.assertTrue(torch.equal(first["random"], dataset[(4, 1)]["random"]))

    def test_d_collate_preserves_zero_weight_padding(self):
        dataset = ExactPairDataset(RandomCPUData(), seed=1, epoch=0)
        batch = collate_stage1_pairs([dataset[(0, 1)], dataset[(0, 0)]])
        self.assertTrue(torch.equal(batch["_pair_weight"], torch.tensor([1.0, 0.0])))
        self.assertEqual(batch["random"].shape, (2, 3))


class TrackerContract(unittest.TestCase):
    def make_config(self, mode="disabled"):
        return {"experiment_id": "STEREO_CUPID_STAGE1_TRAIN_V1",
                "logging": {"tensorboard": False, "wandb_mode": mode, "wandb_project": "fixture-project"}}

    @patch.dict(os.environ, {"SLURM_JOB_ID": "fixture"})
    @patch("subprocess.check_output", return_value="fixture-sha\n")
    def test_transport_init_failure_retains_durable_callback(self, _):
        class CommError(Exception):
            pass
        fake = types.SimpleNamespace(errors=types.SimpleNamespace(CommError=CommError),
                                     init=MagicMock(side_effect=CommError("never persist this")))
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"wandb": fake}):
            adapter = Stage1LoggingAdapter(self.make_config("online"), directory, 0)
            adapter("start", 0, {})
            root = Path(directory)
            self.assertTrue((root / "stereo_observability/events.jsonl").stat().st_size)
            receipt = json.loads((root / "tracking_receipt.json").read_text())
            self.assertEqual(receipt["initialization"], "UNVERIFIED")
            self.assertEqual(receipt["project"], "fixture-project")
            self.assertNotIn("never persist this", (root / "tracking_failures.jsonl").read_text())
            adapter.close()

    @patch.dict(os.environ, {"SLURM_JOB_ID": "fixture"})
    @patch("subprocess.check_output", return_value="fixture-sha\n")
    def test_nontransport_init_failure_is_not_swallowed(self, _):
        class CommError(Exception):
            pass
        fake = types.SimpleNamespace(errors=types.SimpleNamespace(CommError=CommError),
                                     init=MagicMock(side_effect=ValueError("invalid configuration")))
        with tempfile.TemporaryDirectory() as directory, patch.dict("sys.modules", {"wandb": fake}):
            with self.assertRaises(ValueError):
                Stage1LoggingAdapter(self.make_config("online"), directory, 0)
            self.assertTrue((Path(directory) / "stereo_observability/identity.json").exists())

    @patch.dict(os.environ, {"SLURM_JOB_ID": "fixture"})
    @patch("subprocess.check_output", return_value="fixture-sha\n")
    def test_finish_failure_always_closes_writer(self, _):
        for error in (ConnectionError("transport"), ValueError("programming")):
            with tempfile.TemporaryDirectory() as directory:
                adapter = Stage1LoggingAdapter(self.make_config(), directory, 0)
                writer = MagicMock()
                adapter.writer = adapter.callback.writer = writer
                adapter.run = MagicMock()
                adapter.run.finish.side_effect = error
                if isinstance(error, ConnectionError):
                    adapter.close()
                else:
                    with self.assertRaises(ValueError):
                        adapter.close()
                writer.close.assert_called_once()

    @patch.dict(os.environ, {"SLURM_JOB_ID": "fixture"})
    @patch("subprocess.check_output", return_value="fixture-sha\n")
    def test_missing_pose_logs_every_l_metric(self, _):
        with tempfile.TemporaryDirectory() as directory:
            adapter = Stage1LoggingAdapter(self.make_config(), directory, 0)
            adapter("evaluation_status", 1, {"reason": "fixture_missing"})
            records = [json.loads(line) for line in (Path(directory) / "stereo_observability/events.jsonl").read_text().splitlines()]
            statuses = {key for row in records for key in row["payload"] if key.endswith("/status")}
            self.assertEqual(statuses, {"validation/pose/" + key + "/status" for key in METRICS})
            adapter.close()

    @patch.dict(os.environ, {"SLURM_JOB_ID": "fixture"})
    @patch("subprocess.check_output", return_value="fixture-sha\n")
    def test_generator_materialized_once_preserves_failed_denominator(self, _):
        calls = []
        def provider():
            calls.append("called")
            yield {"sample_id": "one", "prediction_status": "OK", "prediction_uses_gt_alignment": False,
                   "prediction": {"rotation": [[1,0,0],[0,1,0],[0,0,1]], "translation": [0,0,2],
                                  "scale": 1, "length_unit": "scene_unit"}, "gt": None}
            yield {"sample_id": "two", "prediction_status": "FAILED", "failure_reason": "fixture"}
        with tempfile.TemporaryDirectory() as directory:
            adapter = Stage1LoggingAdapter(self.make_config(), directory, 0)
            samples = materialize_prediction_samples(provider())
            hook = eval_factory({}, directory, 0)
            result = hook(model=None, step=1, context={"samples": samples})
            adapter("evaluation", 1, {"samples": samples})
            event = json.loads((Path(directory) / "stereo_observability/events.jsonl").read_text().splitlines()[-1])
            self.assertEqual(result["summary"]["num_expected"], 2)
            self.assertEqual(event["details"]["summary"]["num_expected"], 2)
            self.assertEqual(event["details"]["summary"]["metrics"]["translation_norm"]["num_valid"], 1)
            self.assertEqual(event["details"]["summary"]["metrics"]["translation_norm"]["coverage"], 0.5)
            self.assertEqual(calls, ["called"])
            self.assertIsNone(materialize_prediction_samples(None))
            self.assertEqual(materialize_prediction_samples(iter(())), [])
            adapter.close()


if __name__ == "__main__":
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURMD_NODENAME"):
        raise SystemExit("Slurm compute-node CPU test required")
    unittest.main()
