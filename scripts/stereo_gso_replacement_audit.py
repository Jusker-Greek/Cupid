#!/usr/bin/env python3
"""Find bounded same-object replacement pairs for failed fixed-projection GSO pairs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, discover_pairs, load_pair, sha256_file
from stereo_gso_mesh_projection_probe import obj_vertices, project_score


KEY = 'blender_obj_import_hypothesis/+--/saved_x_shift_-0.5B'


def passes(scores):
    return all(side['front_fraction'] >= .99 and side['projected_in_image'] >= 100 and
               side['mask_hit_fraction'] >= .90 and isinstance(side['bbox_mean_abs_error_px'], (int, float)) and
               np.isfinite(side['bbox_mean_abs_error_px']) and side['bbox_mean_abs_error_px'] <= 5.
               for side in (scores['left'], scores['right']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--allpair-objects', required=True)
    parser.add_argument('--allpair-receipt', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--asset-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-attempts-per-object', type=int, default=50)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.max_attempts_per_object < 1:
        parser.error('Slurm allocation and positive attempt cap required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    source_sha = {'manifest': sha256_file(args.manifest), 'allpair_objects': sha256_file(args.allpair_objects),
                  'allpair_receipt': sha256_file(args.allpair_receipt)}
    if source_sha != {'manifest': '0c6c6b9213554c39811323cca15733c19da1d9e848a3f0dd76ea079030e4b625',
                      'allpair_objects': 'af8faa68f93b954f524a1dd5e21ff1426335b9a89bcfc54edd2a1936e2938fa9',
                      'allpair_receipt': 'fc36482625ab2c4015146d1c3496e19973013e36e8aaf938e491de743769abaa'}:
        raise ValueError('frozen manifest or allpair evidence hash changed')
    original = {row['pair_id']: row for row in map(json.loads, Path(args.manifest).open())}
    scores = json.loads(Path(args.allpair_objects).read_text())
    evidence = json.loads(Path(args.allpair_receipt).read_text())
    if len(original) != 1000 or len(scores) != 1000 or evidence['job_id'] != '326950' or evidence['pairs'] != 1000:
        raise ValueError('expected exact 1K frozen pair audit')
    if evidence['manifest_sha256'] != source_sha['manifest'] or not evidence['fixed_hypothesis']:
        raise ValueError('allpair projection used different manifest/hypothesis')
    rejected = [item for item in scores if not passes(item['scores'][KEY])]
    if len(rejected) != 95 or len({item['pair_id'] for item in rejected}) != 95:
        raise ValueError('expected 95 unique rejected 1K pairs')
    needs = defaultdict(list)
    for item in rejected:
        needs[item['object_id']].append(item['pair_id'])
    replacements = []
    assignments = []
    failures = []
    candidate_counts = Counter()
    used_ids = set(original)
    for object_id in sorted(needs):
        mesh = confined_path(args.asset_root, object_id + '/meshes/model.obj')
        raw = obj_vertices(mesh)
        available = []
        inspected = 0
        first_errors = []
        for row in discover_pairs(args.root, 'GSO_1K_200', allowed_objects={object_id}):
            if row['pair_id'] in used_ids or not row['validity']['files_complete']:
                continue
            if inspected >= args.max_attempts_per_object or len(available) >= len(needs[object_id]):
                break
            inspected += 1
            candidate_counts['attempted'] += 1
            try:
                pack = load_pair(row, args.root, hash_assets=True)
                candidate_counts['content_verified'] += 1
                scale = float(row['normalization']['scale'])
                offset = np.asarray(row['normalization']['offset'], dtype=np.float64)
                if scale <= 0 or offset.shape != (3,) or not np.isfinite(scale) or not np.isfinite(offset).all():
                    raise ValueError('invalid normalization')
                points = raw[:, [0, 2, 1]] * np.asarray([1, -1, 1]) * scale + offset
                baseline = float(row['metadata']['baseline'])
                if not np.isfinite(baseline) or baseline <= 0:
                    raise ValueError('invalid baseline')
                axis = np.asarray([1., -1., -1.])
                projected = {side: project_score(points, pack['views'][side], axis, baseline * -.5)
                             for side in ('left', 'right')}
                if not passes(projected):
                    candidate_counts['projection_rejected'] += 1
                    continue
                row['asset_sha256'] = pack['asset_sha256']
                row['validity']['content_verified'] = True
                row['validity']['training_target_ready'] = False
                available.append((row, projected))
                used_ids.add(row['pair_id'])
                candidate_counts['projection_accepted'] += 1
            except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
                candidate_counts['content_or_metadata_failed'] += 1
                if len(first_errors) < 3:
                    first_errors.append({'pair_id': row['pair_id'], 'error': type(exc).__name__ + ': ' + str(exc)})
        for old, pair in zip(needs[object_id], available):
            row, projection = pair
            replacements.append(row)
            assignments.append({'rejected_pair_id': old, 'replacement_pair_id': row['pair_id'],
                                'object_id': object_id, 'split': row['split'],
                                'source_asset_sha256': row['asset_sha256'], 'fixed_projection_scores': projection,
                                'mesh_sha256': sha256_file(mesh)})
            if row['split'] != original[old]['split']:
                raise ValueError('replacement crosses object split')
        for old in needs[object_id][len(available):]:
            failures.append({'rejected_pair_id': old, 'object_id': object_id,
                             'attempted_candidates': inspected, 'first_errors': first_errors,
                             'reason': 'NO_ELIGIBLE_SAME_OBJECT_PAIR_WITHIN_BOUNDED_SEARCH'})
        print(json.dumps({'object_id': object_id, 'needed': len(needs[object_id]),
                          'found': len(available), 'attempted': inspected}), flush=True)
    replacements.sort(key=lambda row: row['pair_id'])
    mapping = output / 'replacement_map.jsonl'
    manifest = output / 'replacement_manifest.jsonl'
    with mapping.open('x') as handle:
        handle.write(''.join(json.dumps(item) + '\n' for item in assignments))
    with manifest.open('x') as handle:
        handle.write(''.join(json.dumps(row) + '\n' for row in replacements))
    with (output / 'unfilled.jsonl').open('x') as handle:
        handle.write(''.join(json.dumps(item) + '\n' for item in failures))
    receipt = {'schema': 'STEREO_GSO_REPLACEMENT_AUDIT_V1', 'status': 'ALL_95_REPLACED_CANDIDATE_ONLY' if not failures else 'PARTIAL_BOUNDED_SEARCH',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'source_sha256': source_sha, 'max_attempts_per_object': args.max_attempts_per_object,
               'rejected_original_pairs': len(rejected), 'replaced_pairs': len(replacements),
               'unfilled_pairs': len(failures), 'candidate_counts': dict(candidate_counts),
               'replacement_map_sha256': sha256_file(mapping),
               'replacement_manifest_sha256': sha256_file(manifest),
               'unfilled_sha256': sha256_file(output / 'unfilled.jsonl'),
               'source_dataset_root': args.root, 'same_object_split_preserved': True,
               'target_ready': False, 'scientific_evidence': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
