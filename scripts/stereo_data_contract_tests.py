#!/usr/bin/env python3
"""Slurm CPU regression checks using temporary synthetic files, not science."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import h5py
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import discover_pairs, load_pair, object_split, confined_path


class RawPairContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='stereo_gso_contract_')
        self.root = Path(self.directory.name)
        self.traj = self.root/'object_a'/'trajectory_0'
        self.traj.mkdir(parents=True)
        (self.traj/'trajectory_info.json').write_text(json.dumps({'resolution':[4,4], 'fov':51, 'num_frames':1}))
        self.rgba = np.full((4,4,4), 255, dtype=np.uint8)
        self.rgba[0,0,3] = 0
        for side in ('left','right'):
            (self.traj/side).mkdir()
            Image.fromarray(self.rgba).save(self.traj/side/'000.png')
            matrix = np.eye(4)[:3]
            matrix[1,1] = -1  # preserve actual audit's reflection class
            np.save(self.traj/side/'000.npy', matrix)
        depths = np.ones((2,4,4),dtype=np.float32)
        depths[:,1,1] = 1e10
        depths[:,1,2] = np.nan
        with h5py.File(self.traj/'0.hdf5','w') as handle:
            handle['depth'] = depths
            handle['colors'] = np.stack([self.rgba,self.rgba])

    def tearDown(self):
        self.directory.cleanup()

    def row(self):
        return list(discover_pairs(self.root,'fixture'))[0]

    def test_numeric_pair_identity_and_sentinel(self):
        row = self.row()
        self.assertEqual(row['frame_id'],'0')
        self.assertTrue(row['validity']['files_complete'])
        pack = load_pair(row,self.root)
        left = pack['views']['left']
        self.assertFalse(left['depth_valid'][0,0])
        self.assertFalse(left['depth_valid'][1,1])
        self.assertFalse(left['depth_valid'][1,2])
        self.assertTrue(left['depth_valid'][2,2])
        self.assertEqual(left['depth'][1,1], np.float32(1e10))
        self.assertEqual(left['rotation_determinant'],-1)
        self.assertFalse(left['proper_rotation'])
        self.assertFalse(pack['validity']['training_target_ready'])

    def test_missing_right_kept_in_denominator(self):
        (self.traj/'right'/'000.png').unlink()
        row = self.row()
        self.assertFalse(row['validity']['files_complete'])
        with self.assertRaises(ValueError):
            load_pair(row,self.root)

    def test_alias_ambiguity_rejected(self):
        Image.fromarray(self.rgba).save(self.traj/'left'/'0.png')
        self.assertFalse(self.row()['validity']['files_complete'])

    def test_per_trajectory_intrinsics_no_default(self):
        row = self.row()
        del row['metadata']['fov']
        with self.assertRaises(KeyError):
            load_pair(row,self.root)

    def test_hdf5_png_mismatch_rejected(self):
        with h5py.File(self.traj/'0.hdf5','r+') as handle:
            handle['colors'][1,0,0,0] = 0
        with self.assertRaises(ValueError):
            load_pair(self.row(),self.root)

    def test_content_hashes_and_fullpixel_map(self):
        pack = load_pair(self.row(),self.root,hash_assets=True)
        self.assertEqual(len(pack['asset_sha256']),6)
        uv = np.array([.5,.25,1.])
        np.testing.assert_array_equal(pack['views']['right']['input_uv_to_fullpixel'] @ uv,[2,1,1])

    def test_object_split_does_not_depend_on_dataset_root(self):
        a = self.row()
        b = list(discover_pairs(self.root,'other_dataset'))[0]
        self.assertNotEqual(a['pair_id'],b['pair_id'])
        self.assertEqual(a['split'],b['split'])
        self.assertEqual(object_split('object_a'),a['split'])

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            confined_path(self.root,'../escape.npy')

    def test_metadata_changed_since_manifest_rejected(self):
        row = self.row()
        (self.traj/'trajectory_info.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'metadata changed'):
            load_pair(row,self.root)


if __name__ == '__main__':
    if not os.environ.get('SLURM_JOB_ID'):
        raise SystemExit('Slurm compute allocation required')
    unittest.main(verbosity=2)
