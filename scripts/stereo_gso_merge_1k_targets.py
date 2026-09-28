#!/usr/bin/env python3
"""Validate and merge 816 base plus 184 increment dense GSO targets."""
from __future__ import annotations

import argparse
from collections import Counter
import errno
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, sha256_file
from stereo_gso_merge_empirical_targets import read_jsonl, validate_npz


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base_root', 'selection_root', 'increment_root', 'output', 'increment_commit'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    parser.add_argument('--shard-count', type=int, default=8)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.shard_count != 8:
        parser.error('Slurm allocation and 8 exact increment shards required')
    base_root = Path(args.base_root).resolve()
    selection_root = Path(args.selection_root).resolve()
    increment_root = Path(args.increment_root).resolve()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'targets').mkdir()
    base_receipt_path = base_root / 'merge_receipt.json'
    base_receipt = json.loads(base_receipt_path.read_text())
    selection_path = selection_root / 'receipt.json'
    selection = json.loads(selection_path.read_text())
    if base_receipt['status'] != 'DENSE_TARGET_CONTENT_VALIDATED' or base_receipt['pairs'] != 816:
        raise ValueError('816 base target receipt invalid')
    if selection['status'] != 'CANDIDATE_1K_PAIR_SET_FROZEN' or selection['combined_pairs'] != 1000:
        raise ValueError('1000-pair selection receipt invalid')
    source_sha = {'base_receipt': sha256_file(base_receipt_path),
                  'selection_receipt': sha256_file(selection_path)}
    manifest_source = selection_root / 'combined_manifest.jsonl'
    if (sha256_file(manifest_source) != selection['output_sha256']['combined_manifest'] or
            sha256_file(base_root / 'merged_manifest.jsonl') != selection['source_sha256']['base_manifest']):
        raise ValueError('combined selection/base manifest linkage broken')
    combined = read_jsonl(manifest_source)
    by_pair = {row['pair_id']: row for row in combined}
    if len(combined) != 1000 or len(by_pair) != 1000 or len({row['object_id'] for row in combined}) != 902:
        raise ValueError('combined manifest identity invalid')
    split_counts = dict(Counter(row['split'] for row in combined))
    if split_counts != selection['split_counts']:
        raise ValueError('combined split counts changed')
    target_sources = []
    base_index = base_root / 'merged_targets.jsonl'
    if sha256_file(base_index) != base_receipt['merged_targets_sha256']:
        raise ValueError('816 base target index hash changed')
    target_sources.extend((row, base_root) for row in read_jsonl(base_index))
    shard_receipts = []
    for index in range(args.shard_count):
        directory = increment_root / f'shard_{index:02d}'
        receipt_path = directory / 'shard_receipt.json'
        receipt = json.loads(receipt_path.read_text())
        if (receipt['schema'] != 'STEREO_GSO_1K_INCREMENT_TARGET_SHARD_V1' or
                receipt['status'] != 'SHARD_TARGETS_PREPARED' or receipt['commit'] != args.increment_commit or
                receipt['shard_index'] != index or receipt['shard_count'] != args.shard_count or receipt['pairs'] != 23 or
                receipt['source_sha256']['selection_receipt'] != source_sha['selection_receipt']):
            raise ValueError(f'increment shard {index} receipt invalid')
        index_path = directory / 'targets/targets.jsonl'
        manifest_path = directory / 'shard_manifest.jsonl'
        summary_path = directory / 'targets/summary.json'
        if (sha256_file(index_path) != receipt['target_index_sha256'] or
                sha256_file(manifest_path) != receipt['shard_manifest_sha256'] or
                sha256_file(summary_path) != receipt['target_summary_sha256']):
            raise ValueError(f'increment shard {index} content hash mismatch')
        summary = json.loads(summary_path.read_text())
        if summary['counts'] != {'prepared': 23, 'failed': 0} or summary['missing_geometry_pairs']:
            raise ValueError(f'increment shard {index} target summary invalid')
        targets = read_jsonl(index_path)
        if len(targets) != 23 or {row['pair_id'] for row in targets} != {row['pair_id'] for row in read_jsonl(manifest_path)}:
            raise ValueError(f'increment shard {index} target coverage invalid')
        target_sources.extend((row, directory / 'targets') for row in targets)
        shard_receipts.append({'path': str(receipt_path), 'sha256': sha256_file(receipt_path),
                               'job_id': receipt['job_id'], 'pairs': receipt['pairs']})
    if len(target_sources) != 1000 or len({row['pair_id'] for row, _ in target_sources}) != 1000:
        raise ValueError('merged 1K target coverage invalid')
    merged_targets = []
    storage_modes = Counter()
    for target, source_root in target_sources:
        row = by_pair[target['pair_id']]
        if target['schema'] != 'STEREO_GSO_DENSE_V1' or target['source_asset_sha256'] != row['asset_sha256']:
            raise ValueError('target/source identity mismatch')
        if any(target[key] != row[key] for key in ('object_id', 'trajectory_id', 'frame_id', 'split')):
            raise ValueError('target split/identity mismatch')
        if target['provenance']['canonical_frame'] != 'GSO_STEREO_MIRRORED_RENDER_UNIT_CUBE_V1':
            raise ValueError('target canonical frame mismatch')
        source = confined_path(source_root, target['npz'])
        if sha256_file(source) != target['sha256']:
            raise ValueError('target NPZ hash mismatch')
        validate_npz(source)
        destination = output / 'targets' / Path(target['npz']).name
        if destination.exists():
            raise ValueError('target NPZ filename collision')
        try:
            os.link(source, destination)
            storage_modes['hardlink'] += 1
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            shutil.copyfile(source, destination)
            storage_modes['copy_cross_device'] += 1
        if sha256_file(destination) != target['sha256']:
            raise ValueError('merged target bytes changed')
        merged_targets.append({**target, 'npz': 'targets/' + destination.name})
    merged_targets.sort(key=lambda row: row['pair_id'])
    if [row['pair_id'] for row in merged_targets] != sorted(by_pair):
        raise ValueError('sorted 1K target identity mismatch')
    manifest_output = output / 'merged_manifest.jsonl'
    index_output = output / 'merged_targets.jsonl'
    with manifest_output.open('x') as handle:
        handle.write(manifest_source.read_text())
    with index_output.open('x') as handle:
        handle.write(''.join(json.dumps(row) + '\n' for row in merged_targets))
    receipt = {'schema': 'STEREO_GSO_REPLACED_1K_TARGET_MERGE_V1', 'status': 'DENSE_TARGET_CONTENT_VALIDATED',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'source_sha256': source_sha, 'increment_commit': args.increment_commit,
               'increment_shards': shard_receipts, 'pairs': 1000, 'objects': 902,
               'split_counts': split_counts, 'base_pairs': 816, 'extra_original_pairs': 89,
               'same_object_replacements': 95, 'original_frozen_1k_pair_identity_changed': True,
               'merged_manifest_sha256': sha256_file(manifest_output),
               'merged_targets_sha256': sha256_file(index_output),
               'target_root': str(output.resolve()), 'storage_modes': dict(storage_modes),
               'historical_renderer_exact_revision_verified': False,
               'original_cupid_canonical_equivalence_verified': False,
               'scientific_evidence': False}
    (output / 'merge_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
