"""Run on a Slurm compute node; no GPU needed."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('resume_policy', Path(__file__).resolve().parents[1] / 'cupid/trainers/stereo_resume.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.old = dict(config=dict(budget={'epochs': 1}, pairs_per_rank=1,
            optimizer={'lr': 1e-5}, objective={'name': 'supervised_suv_fm'}, seed=42),
            train_pairs=809, validation_pairs=93, data_identity={'sha256': 'frozen'})
        self.state = dict(contract=self.old, contract_sha256=hashlib.sha256(
            json.dumps(self.old, sort_keys=True).encode()).hexdigest(), world_size=1, step=809)
        self.new = copy.deepcopy(self.old)
        self.new['config'].update(budget={'updates': 50000}, save_every=5000,
            resume_extension={'source_checkpoint_sha256': 'source'}, checkpoint_evaluation={'validation_pairs': 8})

    def test_exact_resume(self):
        self.assertEqual(module.check_resume_contract(self.state, self.old, 1, 'source'), 'exact')

    def test_authorized_extension(self):
        self.assertEqual(module.check_resume_contract(self.state, self.new, 1, 'source'), 'authorized_budget_extension')

    def test_changed_training_or_data_rejected(self):
        for change in ('optimizer', 'seed', 'data_identity', 'objective'):
            new = copy.deepcopy(self.new)
            if change == 'data_identity':
                new[change] = {'sha256': 'different'}
            else:
                new['config'][change] = 'different'
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.check_resume_contract(self.state, new, 1, 'source')

    def test_wrong_source_topology_integrity_or_budget_rejected(self):
        with self.assertRaises(ValueError):
            module.check_resume_contract(self.state, self.new, 1, 'wrong')
        with self.assertRaises(ValueError):
            module.check_resume_contract(self.state, self.new, 2, 'source')
        self.new['config']['budget'] = {'updates': 809}
        with self.assertRaises(ValueError):
            module.check_resume_contract(self.state, self.new, 1, 'source')
        self.state['contract_sha256'] = 'corrupted'
        with self.assertRaises(ValueError):
            module.check_resume_contract(self.state, self.old, 1, 'source')


if __name__ == '__main__':
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        raise RuntimeError('Tests require a Slurm compute node')
    unittest.main()
