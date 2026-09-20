"""Read-only official asset audit, including interrupted uploads, on Slurm CPU."""
import argparse
import json
import os
from pathlib import Path
import socket

from stereo_runtime_assets import MANIFEST_SHA256, REVISION, release_items, verify_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        raise RuntimeError('SLURM_COMPUTE_NODE_REQUIRED')
    items = release_items()
    # Reserve an exclusive receipt before hashing, preserving partial failure.
    with args.receipt.open('x') as output:
        report = {'schema': 'stereo_cupid_asset_audit/v1', 'revision': REVISION,
                  'manifest_sha256': MANIFEST_SHA256, 'job': os.environ['SLURM_JOB_ID'],
                  'host': socket.gethostname(), 'status': 'AUDITING', 'roots': []}
        output.write(json.dumps(report) + '\n')
        output.flush()
        try:
            for root in args.root:
                group = {'root': str(root.resolve()), 'exists': root.is_dir(), 'files': []}
                report['roots'].append(group)
                for item in items:
                    final = root / item['rfilename']
                    # Bounded lookup: only known official names and their incoming suffixes.
                    paths = [final] + sorted(final.parent.glob(final.name + '.incoming_*'))
                    for path in paths:
                        exists = path.is_file()
                        valid = verify_file(path, item) if exists else False
                        entry = {'release_path': item['rfilename'], 'path': str(path),
                                 'kind': 'final' if path == final else 'incoming',
                                 'size': path.stat().st_size if exists else None,
                                 'status': 'OFFICIAL_HASH_VERIFIED' if valid else
                                           ('HASH_OR_SIZE_MISMATCH' if exists else 'ABSENT')}
                        group['files'].append(entry)
                        print(json.dumps(entry), flush=True)
                group['verified_final_count'] = sum(
                    x['kind'] == 'final' and x['status'] == 'OFFICIAL_HASH_VERIFIED'
                    for x in group['files'])
            report['status'] = 'AUDIT_COMPLETED_NOT_ASSEMBLY_PASS'
        except Exception as error:
            report.update(status='FAILED', first_failed_predicate=str(error))
            raise
        finally:
            output.seek(0)
            output.truncate()
            output.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
