"""Collect bounded, numbered renderer/library excerpts without importing code.

Run on Slurm CPU. Source paths must be observed existing files, not guesses.
This captures current source only; it does not establish historical provenance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket


PATTERN = re.compile(
    r'load_obj|load_blend|obj_import|ObjectLoader|normalize_scene|fixed_rot|'
    r'add_camera_pose|set_matrix_world|matrix_world|intrinsics|sensor_fit|'
    r'pixel_aspect|set_resolution|set_fov|depth|distance|np\.save|write_hdf5|'
    r'^\s*(?:from|import)\s|normaliz|left_pose|right_pose', re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--context', type=int, default=12)
    parser.add_argument('--max-lines', type=int, default=1600)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        raise RuntimeError('SLURM_COMPUTE_NODE_REQUIRED')
    if not 0 <= args.context <= 50 or not 1 <= args.max_lines <= 4000:
        parser.error('Context/line limit outside bounded evidence envelope')
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {'schema': 'stereo_runtime_source_evidence/v1',
               'job': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'status': 'COLLECTING', 'historical_generator_match': 'UNVERIFIED',
               'context_lines': args.context, 'max_lines_per_file': args.max_lines,
               'files': []}
    try:
        for index, path in enumerate(args.source):
            if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
                raise ValueError(f'Source absent or exceeds 4MiB text envelope: {path}')
            raw = path.read_bytes()
            lines = raw.decode('utf-8').splitlines()
            selected = set()
            matches = []
            for number, line in enumerate(lines):
                if PATTERN.search(line):
                    matches.append(number + 1)
                    selected.update(range(max(0, number - args.context),
                                          min(len(lines), number + args.context + 1)))
            indices = sorted(selected)
            truncated = len(indices) > args.max_lines
            indices = indices[:args.max_lines]
            filename = f'source_{index:02d}_excerpts.txt'
            with (args.output / filename).open('x') as output:
                output.write(f'SOURCE={path.resolve()}\nCURRENT_SOURCE_ONLY; HISTORY_UNVERIFIED\n')
                prior = -2
                for number in indices:
                    if number != prior + 1:
                        output.write(f'\n--- {path}:{number + 1} ---\n')
                    output.write(f'{number + 1:6d}  {lines[number]}\n')
                    prior = number
            receipt['files'].append({
                'path': str(path.resolve()), 'size': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(), 'total_source_lines': len(lines),
                'match_lines': matches, 'excerpt_file': filename,
                'emitted_source_lines': len(indices), 'truncated': truncated,
            })
        receipt['status'] = 'EXCERPTS_CAPTURED_NOT_GEOMETRY_VERIFIED'
    except Exception as error:
        receipt.update(status='FAILED', first_failed_predicate=str(error))
        raise
    finally:
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
