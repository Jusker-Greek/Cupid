#!/usr/bin/env python3
"""Verify and merge fixed 326774-selected GSO target shards on a Slurm CPU node."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, sha256_file


def read_jsonl(path):
    with path.open() as handle:
        return [json.loads(line) for line in handle]


def validate_npz(path):
    with np.load(path, allow_pickle=False) as data:
        shapes = {'ss': (1, 64, 64, 64), 'ssuv': (2, 1, 64, 64, 64),
                  'uv_volume': (2, 2, 64, 64, 64), 'crop_xyxy': (2, 4)}
        for key, shape in shapes.items():
            value = np.asarray(data[key])
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError(f'invalid target shape/finiteness: {path} {key}')
            if key in ('ss', 'ssuv') and not np.isin(value, (0, 1)).all():
                raise ValueError(f'nonbinary occupancy: {path} {key}')
            if key == 'uv_volume' and ((value < 0) | (value > 1)).any():
                raise ValueError(f'UV target outside [0,1]: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--shard-count', type=int, required=True)
    parser.add_argument('--shard-commit', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.shard_count < 1:
        parser.error('Slurm allocation and positive shard count required')
    root = Path(args.root).resolve()
    manifest, targets = [], []
    shard_receipts = []
    first = None
    for index in range(args.shard_count):
        directory = root / f'shard_{index:02d}'
        receipt_path = directory / 'shard_receipt.json'
        receipt = json.loads(receipt_path.read_text())
        if receipt['schema'] != 'STEREO_GSO_EMPIRICAL_TARGET_SHARD_V1' or receipt['status'] != 'SHARD_TARGETS_PREPARED':
            raise ValueError(f'shard {index} did not complete')
        if receipt['commit'] != args.shard_commit or receipt['shard_index'] != index or receipt['shard_count'] != args.shard_count:
            raise ValueError(f'shard {index} code/position identity mismatch')
        if receipt['historical_renderer_exact_revision_verified'] or receipt['original_cupid_canonical_equivalence_verified']:
            raise ValueError('unsupported renderer/canonical claim')
        identity = (receipt['source_sha256'], receipt['selection'], receipt['canonical_frame'])
        if first is None:
            first = identity
        elif identity != first:
            raise ValueError(f'shard {index} uses a different source or selection')
        shard_manifest = directory / 'shard_manifest.jsonl'
        shard_index = directory / 'targets/targets.jsonl'
        summary_path = directory / 'targets/summary.json'
        if (sha256_file(shard_manifest) != receipt['shard_manifest_sha256'] or
                sha256_file(shard_index) != receipt['target_index_sha256'] or
                sha256_file(summary_path) != receipt['target_summary_sha256']):
            raise ValueError(f'shard {index} index hash mismatch')
        rows = read_jsonl(shard_manifest)
        entries = read_jsonl(shard_index)
        summary = json.loads(summary_path.read_text())
        if summary['counts'] != {'prepared': len(rows), 'failed': 0} or summary['missing_geometry_pairs']:
            raise ValueError(f'shard {index} target summary invalid')
        by_pair = {row['pair_id']: row for row in rows}
        if len(by_pair) != len(rows) or len({row['object_id'] for row in rows}) != len(rows):
            raise ValueError(f'shard {index} duplicate pair/object')
        if set(by_pair) != set(receipt['source_pairs']) or len(entries) != len(rows):
            raise ValueError(f'shard {index} manifest/receipt coverage mismatch')
        for entry in entries:
            pair_id = entry['pair_id']
            row = by_pair[pair_id]
            if entry['schema'] != 'STEREO_GSO_DENSE_V1' or entry['source_asset_sha256'] != row['asset_sha256']:
                raise ValueError(f'shard {index} target/source mismatch')
            if any(entry[key] != row[key] for key in ('object_id', 'trajectory_id', 'frame_id', 'split')):
                raise ValueError(f'shard {index} split/identity mismatch')
            path = confined_path(root, f'shard_{index:02d}/targets/{entry["npz"]}')
            if sha256_file(path) != entry['sha256']:
                raise ValueError(f'shard {index} NPZ hash mismatch')
            validate_npz(path)
            entry['npz'] = str(path.relative_to(root))
        manifest.extend(rows)
        targets.extend(entries)
        shard_receipts.append({'path': str(receipt_path.relative_to(root)), 'sha256': sha256_file(receipt_path),
                               'job_id': receipt['job_id'], 'pairs': len(rows)})
    if len({row['pair_id'] for row in manifest}) != len(manifest) or len({row['object_id'] for row in manifest}) != len(manifest):
        raise ValueError('cross-shard pair or object duplicate')
    manifest.sort(key=lambda row: row['pair_id'])
    targets.sort(key=lambda row: row['pair_id'])
    if [row['pair_id'] for row in manifest] != [row['pair_id'] for row in targets]:
        raise ValueError('merged target coverage mismatch')
    manifest_text = ''.join(json.dumps(row) + '\n' for row in manifest)
    if hashlib.sha256(manifest_text.encode()).hexdigest() != first[1]['full_eligible_manifest_sha256']:
        raise ValueError('merged manifest differs from frozen eligible selection')
    split_counts = Counter(row['split'] for row in manifest)
    if not split_counts['train'] or not split_counts['validation']:
        raise ValueError('no train/validation object split')
    manifest_path = root / 'merged_manifest.jsonl'
    target_path = root / 'merged_targets.jsonl'
    with manifest_path.open('x') as handle:
        handle.write(manifest_text)
    with target_path.open('x') as handle:
        handle.write(''.join(json.dumps(row) + '\n' for row in targets))
    receipt = {'schema': 'STEREO_GSO_EMPIRICAL_TARGET_MERGE_V1', 'status': 'DENSE_TARGET_CONTENT_VALIDATED',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'merge_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'shard_commit': args.shard_commit, 'source_sha256': first[0], 'selection': first[1],
               'canonical_frame': first[2], 'pairs': len(manifest), 'split_counts': dict(split_counts),
               'shards': shard_receipts, 'merged_manifest_sha256': sha256_file(manifest_path),
               'merged_targets_sha256': sha256_file(target_path), 'target_root': str(root),
               'historical_renderer_exact_revision_verified': False,
               'original_cupid_canonical_equivalence_verified': False,
               'scientific_evidence': False}
    with (root / 'merge_receipt.json').open('x') as handle:
        handle.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
