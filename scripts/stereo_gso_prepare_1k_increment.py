#!/usr/bin/env python3
"""Freeze 89 extra original pairs plus 95 same-object replacements for 1K targets."""
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
from cupid.datasets.stereo_gso import sha256_file

KEY = 'blender_obj_import_hypothesis/+--/saved_x_shift_-0.5B'


def rows(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle]


def passed(score):
    return all(isinstance(side['bbox_mean_abs_error_px'], (int, float)) and
               np.isfinite(side['bbox_mean_abs_error_px']) and side['front_fraction'] >= .99 and
               side['projected_in_image'] >= 100 and side['mask_hit_fraction'] >= .90 and
               side['bbox_mean_abs_error_px'] <= 5. for side in score.values())


def normalization(row):
    return np.asarray([float(row['normalization']['scale']), *row['normalization']['offset']], dtype=np.float64)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original_manifest', 'base_manifest', 'allpair_objects', 'allpair_receipt',
                 'replacement_manifest', 'replacement_map', 'replacement_receipt', 'output'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    source_sha = {name: sha256_file(getattr(args, name)) for name in
                  ('original_manifest', 'base_manifest', 'allpair_objects', 'allpair_receipt',
                   'replacement_manifest', 'replacement_map', 'replacement_receipt')}
    original = rows(args.original_manifest)
    base = rows(args.base_manifest)
    allpair = json.loads(Path(args.allpair_objects).read_text())
    replacement = rows(args.replacement_manifest)
    mapping = rows(args.replacement_map)
    projection_receipt = json.loads(Path(args.allpair_receipt).read_text())
    replacement_receipt = json.loads(Path(args.replacement_receipt).read_text())
    if (len(original), len(base), len(allpair), len(replacement), len(mapping)) != (1000, 816, 1000, 95, 95):
        raise ValueError('expected 1000/816/1000/95/95 frozen inputs')
    if projection_receipt['job_id'] != '326950' or projection_receipt['fixed_gate']['eligible_pairs'] != 905:
        raise ValueError('allpair diagnostic identity changed')
    if replacement_receipt['job_id'] != '326954' or replacement_receipt['status'] != 'ALL_95_REPLACED_CANDIDATE_ONLY':
        raise ValueError('95 same-object replacements were not found')
    if (source_sha['replacement_manifest'] != replacement_receipt['replacement_manifest_sha256'] or
            source_sha['replacement_map'] != replacement_receipt['replacement_map_sha256'] or
            source_sha['original_manifest'] != projection_receipt['manifest_sha256']):
        raise ValueError('source hash linkage broken')
    original_by_id = {row['pair_id']: row for row in original}
    base_by_id = {row['pair_id']: row for row in base}
    replacement_by_id = {row['pair_id']: row for row in replacement}
    if len(original_by_id) != 1000 or len(base_by_id) != 816 or len(replacement_by_id) != 95:
        raise ValueError('duplicate pair identity')
    accepted_original = {item['pair_id']: item['scores'][KEY] for item in allpair
                         if passed(item['scores'][KEY])}
    rejected_original = {item['pair_id'] for item in allpair if item['pair_id'] not in accepted_original}
    if len(accepted_original) != 905 or len(rejected_original) != 95 or not set(base_by_id) <= set(accepted_original):
        raise ValueError('816 base is not a subset of 905 fixed-gate pairs')
    extra_ids = sorted(set(accepted_original) - set(base_by_id))
    if len(extra_ids) != 89:
        raise ValueError('expected 89 extra accepted original pairs')
    mapped_old = set()
    mapped_new = set()
    scores = {pair_id: accepted_original[pair_id] for pair_id in extra_ids}
    for item in mapping:
        old_id, new_id = item['rejected_pair_id'], item['replacement_pair_id']
        if old_id not in rejected_original or old_id in mapped_old or new_id in mapped_new or new_id in original_by_id:
            raise ValueError('replacement pair mapping is not one-to-one')
        old, new = original_by_id[old_id], replacement_by_id[new_id]
        if old['object_id'] != new['object_id'] or old['split'] != new['split'] or new['asset_sha256'] != item['source_asset_sha256']:
            raise ValueError('replacement changes object/split/source identity')
        if not np.allclose(normalization(old), normalization(new), atol=1e-6, rtol=0):
            raise ValueError('replacement object canonical normalization differs: ' + new_id)
        if not passed(item['fixed_projection_scores']):
            raise ValueError('replacement lacks fixed projection agreement')
        mapped_old.add(old_id)
        mapped_new.add(new_id)
        scores[new_id] = item['fixed_projection_scores']
    if mapped_old != rejected_original or len(scores) != 184:
        raise ValueError('replacement coverage incomplete')
    increment = [original_by_id[pair_id] for pair_id in extra_ids] + replacement
    increment.sort(key=lambda row: row['pair_id'])
    combined = base + increment
    combined.sort(key=lambda row: row['pair_id'])
    if len(combined) != 1000 or len({row['pair_id'] for row in combined}) != 1000:
        raise ValueError('combined 1K pair identity invalid')
    objects = {row['object_id'] for row in combined}
    if len(objects) != 902:
        raise ValueError('object coverage changed from 902')
    split_by_object = {}
    for row in combined:
        prior = split_by_object.setdefault(row['object_id'], row['split'])
        if prior != row['split']:
            raise ValueError('object-level split leakage')
    score_index = [{'pair_id': row['pair_id'], 'scores': scores[row['pair_id']]}
                   for row in increment]
    paths = {'increment_manifest': output / 'increment_manifest.jsonl',
             'increment_scores': output / 'increment_scores.jsonl',
             'combined_manifest': output / 'combined_manifest.jsonl'}
    for name, records in (('increment_manifest', increment), ('increment_scores', score_index),
                          ('combined_manifest', combined)):
        with paths[name].open('x') as handle:
            handle.write(''.join(json.dumps(item) + '\n' for item in records))
    receipt = {'schema': 'STEREO_GSO_1K_INCREMENT_SELECTION_V1', 'status': 'CANDIDATE_1K_PAIR_SET_FROZEN',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'source_sha256': source_sha, 'base_pairs': 816, 'extra_original_pairs': 89,
               'same_object_replacements': 95, 'combined_pairs': 1000, 'combined_objects': 902,
               'split_counts': dict(Counter(row['split'] for row in combined)),
               'output_sha256': {name: sha256_file(path) for name, path in paths.items()},
               'historical_renderer_exact_revision_verified': False,
               'original_cupid_canonical_equivalence_verified': False,
               'target_ready': False, 'scientific_evidence': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
