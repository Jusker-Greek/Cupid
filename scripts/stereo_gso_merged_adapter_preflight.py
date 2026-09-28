#!/usr/bin/env python3
"""Read the merged GSO targets through the Stage-1 data factory on Slurm CPU."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import StereoGSOLatents, build_stage1_datasets, sha256_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--expected-pairs', type=int, default=816)
    parser.add_argument('--receipt-output', default=None)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    root = Path(args.root).resolve()
    merge_path = root / 'merge_receipt.json'
    merge = json.loads(merge_path.read_text())
    if merge['status'] != 'DENSE_TARGET_CONTENT_VALIDATED' or merge['pairs'] != args.expected_pairs:
        raise ValueError('expected exact content-validated merge pair count')
    manifest, index = root / 'merged_manifest.jsonl', root / 'merged_targets.jsonl'
    if sha256_file(manifest) != merge['merged_manifest_sha256'] or sha256_file(index) != merge['merged_targets_sha256']:
        raise ValueError('merged manifest/target index hash mismatch')
    config = {'manifest': str(manifest), 'root': args.data_root, 'target_index': str(index),
              'target_root': str(root), 'target_kind': 'dense'}
    pack = build_stage1_datasets(config)
    datasets = {'train': pack['train'], 'validation': pack['validation'],
                'test': StereoGSOLatents(**config, split='test')}
    counts = {split: len(dataset) for split, dataset in datasets.items()}
    if counts != merge['split_counts'] or sum(counts.values()) != merge['pairs']:
        raise ValueError('factory split counts differ from merge')
    samples = {}
    for split, dataset in datasets.items():
        if not dataset:
            raise ValueError('empty split: ' + split)
        samples[split] = []
        for position in sorted({0, len(dataset)-1}):
            item = dataset[position]
            shapes = {key: tuple(item[key].shape) for key in ('images', 'ss', 'ssuv', 'uv_volume')}
            if shapes != {'images': (2, 3, 518, 518), 'ss': (1, 64, 64, 64),
                           'ssuv': (2, 1, 64, 64, 64), 'uv_volume': (2, 2, 64, 64, 64)}:
                raise ValueError('adapter tensor shape mismatch')
            if any(not torch.isfinite(item[key]).all() for key in shapes):
                raise ValueError('adapter tensor nonfinite')
            samples[split].append({'pair_id': item['pair_id'], 'shapes': shapes})
    receipt = {'schema': 'STEREO_GSO_MERGED_ADAPTER_PREFLIGHT_V1', 'status': 'PASS',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'merge_receipt_sha256': sha256_file(merge_path), 'factory_identity': pack['identity'],
               'split_counts': counts, 'samples': samples, 'scientific_evidence': False}
    receipt_path = Path(args.receipt_output) if args.receipt_output else root / 'adapter_preflight_receipt.json'
    with receipt_path.open('x') as handle:
        handle.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
