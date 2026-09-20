#!/usr/bin/env python3
"""Stdlib-only CPU engineering fixture, never a model/scientific result."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.stereo_observability import evaluate_sample, summarize, from_v1_result
from cupid.stereo_observability.logger import StereoLogger, logger_factory
from cupid.stereo_observability.readback import load_events, compare_history, replay

I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def sample():
    gt = dict(rotation=I, translation=[0, 0, 2], scale=2., canonical_id='fixture_axes_origin_scale',
              target_frame='fixture_left_cv', length_unit='m', verified=True,
              metric_unit_verified=True, provenance='analytic_fixture_not_dataset')
    return dict(sample_id='fixture', prediction_status='OK', prediction_uses_gt_alignment=False,
                prediction=copy.deepcopy(gt), gt=gt)


class Metrics(unittest.TestCase):
    def test_analytic_rotation_translation_scale(self):
        s = sample()
        s['prediction'].update(rotation=[[0, -1, 0], [1, 0, 0], [0, 0, 1]], translation=[0, 0, 3], scale=3.)
        m = evaluate_sample(s)['metrics']
        for key, value in dict(rotation_error_deg=90, translation_error=1, translation_norm_ratio=1.5,
                               translation_direction_error_deg=0, scale_relative_error=.5).items():
            self.assertAlmostEqual(m[key]['value'], value)

    def test_missing_gt_keeps_raw_scale(self):
        s = sample(); s['gt'] = None
        m = evaluate_sample(s)['metrics']
        self.assertEqual(m['rotation_error_deg']['status'], 'NOT_APPLICABLE')
        self.assertEqual(m['pose_scale']['value'], 2.)

    def test_common_origin_required(self):
        s = sample(); s['gt']['canonical_id'] = 'different_origin'
        self.assertEqual(evaluate_sample(s)['metrics']['translation_error']['status'], 'UNVERIFIED')

    def test_no_gt_alignment(self):
        s = sample(); s['prediction_uses_gt_alignment'] = True
        self.assertTrue(all(m['value'] is None for m in evaluate_sample(s)['metrics'].values()))

    def test_scene_unit_is_not_metre(self):
        s = sample(); s['prediction']['length_unit'] = s['gt']['length_unit'] = 'scene_unit'
        m = evaluate_sample(s)['metrics']
        self.assertEqual(m['translation_error']['value'], 0)
        self.assertIsNone(m['translation_error_m']['value'])

    def test_reflection_rejected(self):
        s = sample(); s['gt']['rotation'] = [[1, 0, 0], [0, -1, 0], [0, 0, 1]]
        self.assertIsNone(evaluate_sample(s)['metrics']['rotation_error_deg']['value'])

    def test_zero_direction_and_invalid_scalar(self):
        s = sample(); s['gt']['translation'] = [0, 0, 0]; s['prediction']['scale'] = float('nan')
        m = evaluate_sample(s)['metrics']
        self.assertIsNone(m['translation_norm_ratio']['value'])
        self.assertIsNone(m['scale_relative_error']['value'])
        json.dumps(m, allow_nan=False)

    def test_failure_denominator_and_duplicate_rejection(self):
        rows = [evaluate_sample(sample()), evaluate_sample(dict(sample_id='failed', prediction_status='FAILED'))]
        summary = summarize(rows)
        self.assertEqual(summary['metrics']['scale_relative_error']['coverage'], .5)
        self.assertEqual(summary['num_expected'], 2)
        with self.assertRaises(ValueError):
            summarize(rows + rows)

    def test_mixed_units_and_empty_no_fake_mean(self):
        s = sample(); s['sample_id'] = 'scene'; s['prediction']['length_unit'] = s['gt']['length_unit'] = 'scene_unit'
        self.assertIsNone(summarize([evaluate_sample(sample()), evaluate_sample(s)])['metrics']['translation_error']['mean'])
        self.assertIsNone(summarize([])['metrics']['translation_error']['coverage'])

    def test_v1_does_not_assume_canonical(self):
        s = sample()
        v1 = dict(geometry_status='OK', similarity=s['prediction'], length_unit='m')
        m = evaluate_sample(from_v1_result(v1, 'v1', s['gt']))['metrics']
        self.assertEqual(m['translation_error']['status'], 'UNVERIFIED')


class BrokenSink:
    def log(self, payload):
        raise ConnectionError('test-only exception text must not be persisted')


class RecordingSink:
    def __init__(self): self.rows = []
    def log(self, payload): self.rows.append(dict(payload))


class Logging(unittest.TestCase):
    def test_durability_replay_rank_and_exact_readback(self):
        identity = dict(experiment_id='STEREO_CUPID_STAGE1_TRAIN_V1', attempt_id='FIXTURE_ONLY',
                        git_commit='fixture', git_tree='fixture', slurm_job_id=os.environ['SLURM_JOB_ID'])
        with tempfile.TemporaryDirectory(prefix='stereo_L_fixture_') as directory:
            root = Path(directory)
            logger_factory({}, root/'rank1', 1)('anything', 0, {})
            self.assertFalse((root/'rank1').exists())
            log = StereoLogger(root, identity, wandb_run=BrokenSink())
            log('loss', 1, dict(split='train', total=2., components={'ss': 1., 'uv': 1.}, epoch=.1, learning_rates=[.001]))
            log('optimizer', 1, dict(applied=True, grad_norm=3., amp_log_scale=20.))
            log('checkpoint', 1, dict(path='fixture.pt', status='WRITTEN'))
            log('evaluation', 1, dict(samples=[sample()]))
            log('loss', 2, dict(split='validation', total=float('nan'), components={}, epoch=.1))
            _, events = load_events(log.root)
            self.assertEqual(len(events), 5)
            self.assertNotIn('test-only exception text', (log.root/'sink_failures.jsonl').read_text())
            self.assertIsNone(events[-1]['payload'].get('validation/loss_total'))
            sink = RecordingSink(); replay(log.root, sink)
            self.assertEqual(compare_history(events, sink.rows)['status'], 'READBACK_PASS')
            self.assertEqual(compare_history(events, sink.rows + sink.rows)['status'], 'READBACK_PASS')
            self.assertEqual(compare_history(events, sink.rows[:-1])['status'], 'UNVERIFIED')
            altered = copy.deepcopy(sink.rows); altered[0]['train/loss_total'] = 0
            self.assertEqual(compare_history(events, altered)['status'], 'UNVERIFIED')
            self.assertEqual(compare_history(events, sink.rows)['s07_status'], 'UNVERIFIED')
            with self.assertRaises(FileExistsError): StereoLogger(root, identity)


if __name__ == '__main__':
    if not os.environ.get('SLURM_JOB_ID'):
        raise SystemExit('Run on a Slurm compute node; local/login execution forbidden')
    unittest.main(verbosity=2)
