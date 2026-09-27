#!/usr/bin/env python3
"""Re-read a frozen GSO 1K candidate through the D pair contract on Slurm CPU.

The output is a content-verified data manifest, never a training target or a
canonical-camera conversion. Every source candidate remains in the denominator.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import SCHEMA, load_pair, object_split, sha256_file


ASSET_KEYS = {'left_png': 'left_rgba', 'left_npy': 'left_extrinsics',
              'right_png': 'right_rgba', 'right_npy': 'right_extrinsics',
              'depth_hdf5': 'depth'}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--candidate-receipt', required=True)
    parser.add_argument('--candidate-manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Run inside a Slurm compute allocation')
    config = json.loads(Path(args.config).read_text())
    source = json.loads(Path(args.candidate_receipt).read_text())
    if source.get('schema') != 'STEREO_GSO_1K_CANDIDATE_RECEIPT_V1' or source.get('status') != 'CANDIDATE_ONLY':
        parser.error('Expected the frozen 1K candidate receipt')
    if source['root'] != config['root'] or source['pairs_sha256'] != sha256_file(args.candidate_manifest):
        parser.error('Candidate root or manifest hash differs from the frozen receipt')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    counts = Counter()
    split_objects = defaultdict(set)
    image_splits = {}
    seen = set()
    with Path(args.candidate_manifest).open() as input_rows, (output / 'pairs.jsonl').open('x') as passed, \
            (output / 'failures.jsonl').open('x') as failures:
        for line in input_rows:
            item = json.loads(line)
            counts['candidate_pairs'] += 1
            pair_id = item['pair_id']
            if pair_id in seen:
                raise ValueError('duplicate pair identity: ' + pair_id)
            seen.add(pair_id)
            if item['schema'] != 'STEREO_GSO_1K_CANDIDATE_V1':
                raise ValueError('unexpected candidate row schema')
            if item['split'] != object_split(item['object_id'], config['split_seed'], config['split_fractions']):
                raise ValueError('object split differs from D contract: ' + pair_id)
            split_objects[item['split']].add(item['object_id'])
            metadata = item['metadata']
            row = {
                'schema': SCHEMA, 'dataset_id': config['dataset_id'], 'pair_id': pair_id,
                'object_id': item['object_id'], 'trajectory_id': item['trajectory_id'],
                'frame_id': item['frame_id'], 'split': item['split'],
                'split_policy': {'seed': config['split_seed'],
                                 'fractions': config['split_fractions'], 'key': 'object_id'},
                'assets': {destination: item['assets'][source_key]
                           for source_key, destination in ASSET_KEYS.items()},
                'metadata': metadata, 'normalization': metadata.get('normalization'),
                'unit': {'length': 'scene_unit', 'metric_meters_verified': False},
                'provenance': {
                    'metadata_path': item['metadata_path'],
                    'metadata_sha256': item['metadata_sha256'],
                    'renderer_exact_revision': metadata.get('renderer_revision'),
                    'renderer_version': metadata.get('renderer_version'),
                    'historical_renderer_verified': False,
                    'source_candidate_manifest_sha256': source['pairs_sha256'],
                },
                'validity': {'files_complete': True, 'errors': [],
                             'content_verified': False, 'training_target_ready': False},
            }
            try:
                pack = load_pair(row, config['root'],
                                 depth_background=config['depth_background_exclusive'],
                                 hash_assets=True)
                expected = item['content_diagnostics']
                if pack['asset_sha256']['trajectory_metadata'] != item['metadata_sha256']:
                    raise ValueError('trajectory metadata hash differs from candidate')
                for side in ('left', 'right'):
                    if pack['asset_sha256'][side + '_rgba'] != expected[side]['image_sha256']:
                        raise ValueError(side + ' image hash differs from candidate')
                    if pack['asset_sha256'][side + '_extrinsics'] != expected[side]['matrix_sha256']:
                        raise ValueError(side + ' camera hash differs from candidate')
                if pack['asset_sha256']['depth'] != expected['depth_sha256']:
                    raise ValueError('depth hash differs from candidate')
                row['validity'] = pack['validity']
                row['provenance'] = pack['provenance']
                row['asset_sha256'] = pack['asset_sha256']
                row['provenance']['source_candidate_manifest_sha256'] = source['pairs_sha256']
                row['view_diagnostics'] = {
                    side: {'proper_rotation': view['proper_rotation'],
                           'rotation_determinant': view['rotation_determinant'],
                           'K_status': view['K_status'], 'K_fullpixel': view['K_fullpixel'].tolist(),
                           'w2c_saved': view['w2c_saved'].tolist(),
                           'foreground_pixels': int(view['mask'].sum()),
                           'valid_depth_pixels': int(view['depth_valid'].sum())}
                    for side, view in pack['views'].items()}
                for side in ('left', 'right'):
                    digest = pack['asset_sha256'][side + '_rgba']
                    prior = image_splits.setdefault(digest, item['split'])
                    if prior != item['split']:
                        raise ValueError('image duplicates across object splits')
                counts['content_verified'] += 1
                counts['proper_rotation_pairs'] += int(pack['validity']['proper_rotations'])
                counts['shared_mesh_byte_equal'] += int(item.get('shared_mesh_byte_equal') is True)
            except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
                row['validity']['errors'].append(type(exc).__name__ + ': ' + str(exc))
                counts['content_failed'] += 1
                failures.write(json.dumps({'pair_id': pair_id, 'error': row['validity']['errors'][-1]}) + '\n')
            passed.write(json.dumps(row, allow_nan=False) + '\n')
            if counts['candidate_pairs'] % 100 == 0:
                passed.flush()
                print(json.dumps(dict(counts)), flush=True)
    if counts['candidate_pairs'] != source['selected_pairs']:
        raise ValueError('candidate row count differs from frozen receipt')
    summary = {
        'schema': 'STEREO_GSO_1K_D_CROSS_AUDIT_V1',
        'status': 'COMPLETED_WITH_TARGET_BLOCKER',
        'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
        'started_at': started, 'ended_at': datetime.now(timezone.utc).isoformat(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
        'source_receipt_sha256': sha256_file(args.candidate_receipt),
        'source_manifest_sha256': source['pairs_sha256'],
        'd_manifest_sha256': sha256_file(output / 'pairs.jsonl'),
        'counts': dict(counts),
        'split_object_counts': {key: len(value) for key, value in split_objects.items()},
        'object_split_disjoint': not any(split_objects[a] & split_objects[b]
                                         for a, b in (('train','validation'),('train','test'),('validation','test'))),
        'historical_renderer_verified': False,
        'canonical_occupancy_verified': False,
        'canonical_to_cv_verified': False,
        'target_ready': False, 'scientific_evidence': False,
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
