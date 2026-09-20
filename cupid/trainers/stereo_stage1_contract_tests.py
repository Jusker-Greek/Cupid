"""CPU sampler/resume interface fixtures; not a model/GPU smoke.

Run only on a Slurm compute node:
python -m cupid.trainers.stereo_stage1_contract_tests
"""
import os
import random
import unittest

import numpy as np
import torch

from .stereo_stage1 import ExactBatchSampler, ExactPairDataset
from ..datasets.stereo_gso import collate_stage1_pairs


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


if __name__ == "__main__":
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURMD_NODENAME"):
        raise SystemExit("Slurm compute-node CPU test required")
    unittest.main()
